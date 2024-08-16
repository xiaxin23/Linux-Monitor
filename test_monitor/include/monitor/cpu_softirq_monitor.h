// CPU软中断

#pragma once
#include <string>
#include <unordered_map>

#include <boost/chrono.hpp>

#include "monitor/monitor_inter.h"

#include "monitor_info.grpc.pb.h"
#include "monitor_info.pb.h"

namespace monitor {
class CpuSoftIrqMonitor : public MonitorInter {
  // cpu软中断监控的性能类
  struct SoftIrq {
    std::string cpu_name;
    int64_t hi;
    int64_t timer;   // 定时中断
    int64_t net_tx;  // 网络发送
    int64_t net_rx;  // 网络接收
    int64_t block;
    int64_t irq_poll;
    int64_t tasklet;
    int64_t sched;  // 内核调度
    int64_t hrtimer;
    int64_t rcu;  // RCU锁
    boost::chrono::steady_clock::time_point timepoint;
  };

 public:
  CpuSoftIrqMonitor() {}
  void UpdateOnce(monitor::proto::MonitorInfo* monitor_info);
  void Stop() override {}

 private:
  std::unordered_map<std::string, struct SoftIrq> cpu_softirqs_;
};

}  // namespace monitor
