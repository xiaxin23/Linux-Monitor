#pragma once
#include <memory>
#include <thread>
#include <vector>

#include "client/rpc_client.h"
#include "monitor/cpu_load_monitor.h"
#include "monitor/cpu_softirq_monitor.h"
#include "monitor/cpu_stat_monitor.h"
#include "monitor/mem_monitor.h"
#include "monitor/monitor_inter.h"
#include "monitor/net_monitor.h"

#include "monitor_info.grpc.pb.h"
#include "monitor_info.pb.h"

int main() {
  // 智能指针容器 runners_  不用担心delete空间
  // 其中存放被监控的各个模块的实例化对象指针，通过调用指针操作实例化对象
  std::vector<std::shared_ptr<monitor::MonitorInter>> runners_;
  runners_.emplace_back(new monitor::CpuSoftIrqMonitor());
  runners_.emplace_back(new monitor::CpuLoadMonitor());
  runners_.emplace_back(new monitor::CpuStatMonitor());
  runners_.emplace_back(new monitor::MemMonitor());
  runners_.emplace_back(new monitor::NetMonitor());

  monitor::RpcClient rpc_client_;
  char* name = getenv("USER");
  // 构建线程
  std::unique_ptr<std::thread> thread_ = nullptr;
  // 此处的lamdba式子[&]可以调用外部参数
  // 创建线程的回调函数
  thread_ = std::make_unique<std::thread>([&]() {
    while (true) {
      // monitor_info作为传出参数，承担着像对侧传递性能数据的任务
      monitor::proto::MonitorInfo monitor_info;
      monitor_info.set_name(std::string(name));
      for (auto& runner : runners_) {
        runner->UpdateOnce(&monitor_info);
      }

      // 传送给gRPC
      rpc_client_.SetMonitorInfo(monitor_info);
      std::this_thread::sleep_for(std::chrono::seconds(3));
    }
  });

  // 主线程阻塞等待
  thread_->join();
  return 0;
}
