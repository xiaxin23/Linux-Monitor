#pragma once

#include <string>
#include <unordered_map>

#include "monitor/monitor_inter.h"

#include "monitor_info.grpc.pb.h"
#include "monitor_info.pb.h"

namespace monitor {
class MemMonitor : public MonitorInter {
  // 构造内存相关参数的类
  struct MenInfo {
    int64_t total;  // 总内存大小
    int64_t free;   // 未使用内存大小
    int64_t avail;  // 不交换的情况下，新的应用最大可用内存大小
    int64_t buffers;  // 块设备 缓存大小
    int64_t cached;   // 普通文件缓冲区大小
    int64_t swap_cached;
    int64_t active;
    int64_t in_active;
    int64_t active_anon;
    int64_t inactive_anon;
    int64_t active_file;
    int64_t inactive_file;
    int64_t dirty;      // 脏位，需要写回磁盘的大小
    int64_t writeback;  // 正在被写回的内存区的大小
    int64_t anon_pages;
    int64_t mapped;
    int64_t kReclaimable;
    int64_t sReclaimable;
    int64_t sUnreclaim;
  };

 public:
  MemMonitor() {}
  void UpdateOnce(monitor::proto::MonitorInfo* monitor_info);
  void Stop() override {}
};

}  // namespace monitor