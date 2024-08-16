#pragma once
#include <string>

#include "monitor/monitor_inter.h"

#include "monitor_info.grpc.pb.h"
namespace monitor {

// 抽象类
class MonitorInter {
 public:
  // 构造函数不可为虚函数
  MonitorInter() {}

  // 虚函数规范后续继承类的实现，接口复用

  // 析构函数可以为虚函数
  virtual ~MonitorInter() {}
  // 每3秒运行一次此函数
  virtual void UpdateOnce(monitor::proto::MonitorInfo* monitor_info) = 0;
  virtual void Stop() = 0;
};
}  // namespace monitor