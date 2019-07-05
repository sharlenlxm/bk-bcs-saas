--[[
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
Copyright (C) 2017-2019 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
]]
config = {
  env = "dev",
  static_dir = "./frontend",
  log_dir = "./logs",
  allow_hosts = {
    [==[.*]==]
  },
  -- TODO: 需要解决动态IP
  ns_ip = "172.19.0.5",
  ns_port = 8600,
  ns_domain = "service.bkdevops"
}

string = require("string")
math = require("math")
json = require("cjson.safe")
uuid = require("resty.jit-uuid")
ck = require("resty.cookie")
resolver = require("resty.dns.resolver")
http = require("resty.http")
md5 = require("resty.md5")
cookieUtil = require("cookie_util")

math.randomseed(os.time())
uuid.seed()
