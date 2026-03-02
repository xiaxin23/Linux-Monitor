#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import argparse
import random
from pathlib import Path
from contextlib import nullcontext
from PIL import Image

import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms

from diffusers import StableDiffusion3Pipeline
from sd3_dit_head import SD3DiTPredictionHead


# ---------------- Dataset: Raw Images & Prompts ----------------
class RawImagePromptDataset(Dataset):
    """
    在线读取原始图片和对应的文本 prompt 文件
    期望结构: images/0001.png, prompts/0001.txt
    """
    def __init__(self, image_dir: str, prompt_dir: str, image_size: int = 1024):
        self.image_dir = Path(image_dir)
        self.prompt_dir = Path(prompt_dir)
        self.image_size = image_size
        
        # 匹配图片和 Prompt (通过文件名 stem)
        valid_exts = {'.png', '.jpg', '.jpeg'}
        self.samples = []
        
        for img_path in self.image_dir.iterdir():
            if img_path.suffix.lower() in valid_exts:
                prompt_path = self.prompt_dir / f"{img_path.stem}.txt"
                if prompt_path.exists():
                    self.samples.append((str(img_path), str(prompt_path)))
                    
        print(f"✅ Found {len(self.samples)} aligned image-prompt pairs.")
        if len(self.samples) == 0:
            raise RuntimeError("No matching images and prompts found. Check your directories.")

        # 图像预处理: 缩放/裁剪到 1024x1024 并归一化到 [-1, 1]
        self.transform = transforms.Compose([
            transforms.Resize(self.image_size, interpolation=transforms.InterpolationMode.BILINEAR),
            transforms.CenterCrop(self.image_size),
            transforms.ToTensor(),
            transforms.Normalize([0.5], [0.5])
        ])

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx: int):
        img_path, prompt_path = self.samples[idx]
        
        # 读取图像
        image = Image.open(img_path).convert("RGB")
        pixel_values = self.transform(image)
        
        # 读取文本
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read().strip()
            
        return {
            "pixel_values": pixel_values,
            "prompt": prompt_text
        }

def collate_fn(batch):
    pixel_values = torch.stack([b["pixel_values"] for b in batch], dim=0)
    prompts = [b["prompt"] for b in batch]
    return {"pixel_values": pixel_values, "prompts": prompts}


# ---------------- Training ----------------
def train_sd3_dit_head_online(args):
    os.makedirs(args.save_dir, exist_ok=True)
    torch.manual_seed(args.seed)
    random.seed(args.seed)

    device = torch.device(args.device)
    compute_dtype = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}[args.dtype]
    param_dtype = torch.float32 if compute_dtype == torch.float16 else compute_dtype

    # =========================================================================
    # 1. 加载云端主干大模型 (Teacher) - 纯推理模式，极大节省显存
    # =========================================================================
    print("\n[Init] Loading Full SD3 Teacher Pipeline in memory...")
    pipe = StableDiffusion3Pipeline.from_pretrained(args.model_path, torch_dtype=compute_dtype)
    pipe = pipe.to(device)
    
    # 冻结所有主模型参数
    pipe.vae.requires_grad_(False)
    pipe.transformer.requires_grad_(False)
    pipe.text_encoder.requires_grad_(False)
    pipe.text_encoder_2.requires_grad_(False)
    if pipe.text_encoder_3 is not None:
        pipe.text_encoder_3.requires_grad_(False)
        
    pipe.vae.eval()
    pipe.transformer.eval()

    # 设置推测 100 步
    pipe.scheduler.set_timesteps(100, device=device)
    timesteps_array = pipe.scheduler.timesteps # Shape: [100], 降序 (例如 999 -> 0)
    
    # 根据用户设置，决定从哪个时间步区间抽样 (0 是高噪声早期，99 是低噪声后期)
    start_idx = int(100 * args.step_frac_start)
    end_idx = 99
    print(f"🕒 Sampling timesteps from index {start_idx} to {end_idx} (out of 100 steps).")

    # =========================================================================
    # 2. 构建 Dataset & DataLoader
    # =========================================================================
    dataset = RawImagePromptDataset(image_dir=args.image_dir, prompt_dir=args.prompt_dir, image_size=1024)
    dataloader = DataLoader(
        dataset, batch_size=args.batch_size, shuffle=True, 
        num_workers=args.num_workers, pin_memory=True, collate_fn=collate_fn
    )

    # =========================================================================
    # 3. 构建 边缘预测头 (Student)
    # =========================================================================
    print("[Init] Building Prediction Head...")
    head = SD3DiTPredictionHead.from_pretrained(
        model_path=args.model_path, num_blocks=args.num_blocks, 
        device=str(device), load_dtype=compute_dtype, torch_dtype=param_dtype
    )
    head.train()

    optimizer = torch.optim.AdamW(head.parameters(), lr=args.lr, weight_decay=1e-2)
    pred_crit = nn.MSELoss()

    # 混合精度上下文
    use_autocast = (device.type == "cuda") and (compute_dtype in (torch.float16, torch.bfloat16))
    autocast_ctx = lambda: torch.amp.autocast("cuda", dtype=compute_dtype) if use_autocast else nullcontext()

    print("\n================ Training Config ================")
    print(f"image_dir         : {args.image_dir}")
    print(f"prompt_dir        : {args.prompt_dir}")
    print(f"compute_dtype     : {compute_dtype}")
    print(f"step_frac_start   : {args.step_frac_start} (T_index {start_idx} to {end_idx})")
    print("=================================================\n")

    global_step = 0

    for epoch in range(args.epochs):
        running_loss = 0.0
        
        for it, batch in enumerate(dataloader):
            pixel_values = batch["pixel_values"].to(device, dtype=compute_dtype, non_blocking=True)
            prompts = batch["prompts"]
            bsz = pixel_values.shape[0]

            optimizer.zero_grad(set_to_none=True)

            # -----------------------------------------------------------------
            # [无梯度域] Teacher 处理: VAE编码 + 文本编码 + 加噪 + Teacher前向
            # -----------------------------------------------------------------
            with torch.no_grad(), autocast_ctx():
                # 1. VAE 编码原图得到 Latent (x_0)
                latents = pipe.vae.encode(pixel_values).latent_dist.sample()
                latents = latents * pipe.vae.config.scaling_factor

                # 2. 文本编码：适配新版 diffusers 返回 4 个值的接口
                prompt_out = pipe.encode_prompt(
                    prompt=prompts, prompt_2=None, prompt_3=None, device=device
                )
                prompt_embeds = prompt_out[0]         # 提取正向文本特征
                pooled_prompt_embeds = prompt_out[2]  # 提取正向池化特征

                # 3. 随机抽取时间步 t 并加噪得到 x_t
                # 随机抽取 index，并获取对应的实际 t 值
                t_idx = torch.randint(start_idx, end_idx + 1, (bsz,), device=device)
                t = timesteps_array[t_idx] 
                
                noise = torch.randn_like(latents)
                # --- SD3 Flow Matching 手动加噪 ---
                # 将时间步 t (通常是 0~1000) 归一化为 0~1 之间的 sigma
                # .view(-1, 1, 1, 1) 是为了对齐 latents 的维度 (bsz, C, H, W) 方便广播计算
                sigmas = (t / pipe.scheduler.config.num_train_timesteps).view(-1, 1, 1, 1).to(device=device, dtype=compute_dtype)
                xt = (1.0 - sigmas) * latents + sigmas * noise      

                # 4. 提取 2D RoPE (若模型不支持则设为 None)
                H, W = latents.shape[2], latents.shape[3]
                if hasattr(pipe.transformer, '_get_rotary_pos_embed'):
                    image_rotary_emb = pipe.transformer._get_rotary_pos_embed(H, W)
                    image_rotary_emb = image_rotary_emb.to(device=device, dtype=compute_dtype)
                else:
                    image_rotary_emb = None

                # 5. Teacher 主干网络前向，获取目标 m_t
                mt_teacher = pipe.transformer(
                    hidden_states=xt,
                    encoder_hidden_states=prompt_embeds,
                    pooled_projections=pooled_prompt_embeds,
                    timestep=t,
                    return_dict=False
                )[0]

            # -----------------------------------------------------------------
            # [梯度域] Student 预测头前向与损失计算
            # -----------------------------------------------------------------
            with autocast_ctx():
                # 传入 x_t, 文本特征, 时间步 t, 以及 2D RoPE
                m_hat = head(
                    latent_t=xt,
                    timestep=t,
                    text_embeds=prompt_embeds,
                    pooled_text_embeds=pooled_prompt_embeds,
                    image_rotary_emb=image_rotary_emb, 
                )

                loss = pred_crit(m_hat.float(), mt_teacher.float())

            if not torch.isfinite(loss):
                print(f"⚠️ Skip non-finite loss at step={global_step}: {loss.item()}")
                continue

            # 反向传播与优化
            loss.backward()
            if args.grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(head.parameters(), max_norm=args.grad_clip)
            optimizer.step()

            global_step += 1
            running_loss += float(loss.item())

            if (it + 1) % args.log_every == 0:
                print(
                    f"[Epoch {epoch+1}/{args.epochs}] Iter {it+1}/{len(dataloader)} | "
                    f"Loss: {running_loss/args.log_every:.6f} | "
                    f"Last T-Index: {t_idx[0].item()} (t={t[0].item():.1f})"
                )
                running_loss = 0.0

        # 保存 Checkpoint
        ckpt_path = os.path.join(args.save_dir, f"sd3_dit_head_epoch{epoch+1}.pt")
        torch.save({"epoch": epoch + 1, "state_dict": head.state_dict()}, ckpt_path)
        print(f"💾 Saved checkpoint: {ckpt_path}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--model_path", type=str, required=True)
    p.add_argument("--image_dir", type=str, required=True)
    p.add_argument("--prompt_dir", type=str, required=True)
    p.add_argument("--save_dir", type=str, required=True)
    p.add_argument("--device", type=str, default="cuda:0")
    
    p.add_argument("--num_blocks", type=int, default=1)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch_size", type=int, default=1)
    p.add_argument("--lr", type=float, default=5e-5)
    
    p.add_argument("--dtype", type=str, default="bf16", choices=["fp16", "bf16", "fp32"])
    p.add_argument("--grad_clip", type=float, default=1.0)
    p.add_argument("--log_every", type=int, default=10)
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--seed", type=int, default=42)

    # 从 T100 的哪个比例开始抽 (0.6 意味着从索引 60 即后 40 步开始抽)
    p.add_argument("--step_frac_start", type=float, default=0.6)
    return p.parse_args()


if __name__ == "__main__":
    train_sd3_dit_head_online(parse_args())
