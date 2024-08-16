#pragma once

#include <string>
#include <unordered_map>

#include <boost/chrono.hpp>

#include "monitor/monitor_inter.h"

#include "monitor_info.grpc.pb.h"
#include "monitor_info.pb.h"

namespace monitor {
class NetMonitor : public MonitorInter {
  // 网络属性相关类
  struct NetInfo {
    std::string name;
    int64_t rcv_bytes;    // 接收字节数
    int64_t rcv_packets;  // 接收包数
    int64_t err_in;       // 接收错误总数
    int64_t drop_in;      // 入口丢包总数
    int64_t snd_bytes;    // 发送字节数
    int64_t snd_packets;  // 发送包数
    int64_t err_out;      // 发送错误总数
    int64_t drop_out;     // 出口丢包总数
    boost::chrono::steady_clock::time_point timepoint;
  };

 public:
  NetMonitor() {}
  void UpdateOnce(monitor::proto::MonitorInfo* monitor_info);
  void Stop() override {}

 private:
  // 同样的哈希映射
  std::unordered_map<std::string, struct NetInfo> net_info_;
};

}  // namespace monitor