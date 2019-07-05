/*
 * Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 * Copyright (C) 2017-2019 THL A29 Limited, a Tencent company. All rights reserved.
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * http://opensource.org/licenses/MIT
 * Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
 * an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
 * specific language governing permissions and limitations under the License.
 *
 */

package com.tencent.devops.common.api.pojo

import com.fasterxml.jackson.annotation.JsonIgnore
import com.tencent.devops.common.api.enum.AgentStatus
import io.swagger.annotations.ApiModel
import io.swagger.annotations.ApiModelProperty

@ApiModel("第三方Agent数据返回包装模型")
data class AgentResult<out T>(
    @ApiModelProperty("状态码", required = true)
    val status: Int,
    @ApiModelProperty("错误信息", required = false)
    val message: String? = null,
    @ApiModelProperty("Agent状态", required = false)
    val agentStatus: AgentStatus?,
    @ApiModelProperty("数据", required = false)
    val data: T? = null
) {
    constructor(status: AgentStatus, data: T) : this(0, null, status, data)
    constructor(status: Int, message: String): this(status, message, null, null)

    @JsonIgnore
    fun isNotOk(): Boolean {
        return status != 0
    }

    @JsonIgnore
    fun isAgentNotOK(): Boolean {
        if (agentStatus == null) {
            return true
        }
        return isAgentDelete()
    }

    @JsonIgnore
    fun isAgentDelete(): Boolean {
        if (agentStatus == null) {
            return false
        }
        return agentStatus == AgentStatus.DELETE
    }
}