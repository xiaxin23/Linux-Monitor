#pragma once

#include <string>
#include <unordered_map>

#include "monitor/monitor_inter.h"

#include "monitor_info.grpc.pb.h"
#include "monitor_info.pb.h"

namespace monitor {
class CpuStatMonitor : public MonitorInter {
  // 私有的Cpu状态类，内涵从/proc/stat读取到的各种性能数据
  struct CpuStat {
    std::string cpu_name;
    float user;
    float system;
    float idle;
    float nice;
    float io_wait;
    float irq;
    float soft_irq;
    float steal;
    float guest;
    float guest_nice;
  };

 public:
  CpuStatMonitor() {}

  // 构造继承的抽象函数
  void UpdateOnce(monitor::proto::MonitorInfo* monitor_info);
  void Stop() override {}

 private:
  // 定义一个字符串到CPU状态类的哈希映射
  std::unordered_map<std::string, struct CpuStat> cpu_stat_map_;
};

}  // namespace monitor
