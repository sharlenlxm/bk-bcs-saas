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

package com.tencent.devops.project.pojo

import io.swagger.annotations.ApiModel
import io.swagger.annotations.ApiModelProperty

@ApiModel("最新动态-显示模型")
data class OPActivityVO(
    @ApiModelProperty("主键ID")
    val id: Long,
    @ApiModelProperty("名称")
    val name: String,
    @ApiModelProperty("链接")
    val link: String,
    @ApiModelProperty("类型")
    val type: String,
    @ApiModelProperty("状态")
    val status: String,
    @ApiModelProperty("创建人")
    val creator: String,
    @ApiModelProperty("创建时间")
    val createTime: String
)