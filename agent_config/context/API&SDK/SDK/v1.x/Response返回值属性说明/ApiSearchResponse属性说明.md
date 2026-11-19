[TOC]

# 表单/审批 检索相关接口
### ApiSearchResponse

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|code   |String   |状态码（详情请见[状态码说明](https://cxapi.chaoxing.com/web/#/653656294/207980774 "状态码说明")）   |
|success   |Boolean   |成功标识（true / false）   |
|msg   |String   |接口返回的信息   |
|data   |ApiSearchResponseData   |接口返回的数据   |

### ApiSearchResponseData（返回值数据）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|total   |Integer   |总条数   |
|totalPage   |Integer   |总页数   |
|sortValues   |String   |接口返回的数据   |
|dataList   |List<ApiFormsUser>   |表单数据集合   |
|resultMap   |Map<String, ApiStatisticsInfo>   |汇总统计接口返回结果   |
|uid   |Long   |用户uid   |
|signature   |String   |手写签名组件中保存的用户签名地址   |
|approveSignature   |String   |审批流程中保存的用户签名地址   |
|approveTypeList   |List<ApproveType>   |审批类型列表   |
|approveStepBackList   |List<ApproveNodeInfo>   |审批当前节点可进行回退的节点列表（获取审批回退列表接口）   |
|approveBackConfig   |Integer   |审批回退节点配置 <br> 1：审批人自选回退节点 <br>-1：回退上一节点<br>（获取审批回退列表接口）  |
|approveBackModifyList   |List<ApproveNodeInfo>   |审批打回修改时可选择的节点列表（获取审批打回修改列表接口）；SDK v1.10.1 起支持   |

### ApiFormUser（表单记录）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|uid   |Long   |提交人uid（审批发起人）   |
|fid   |Integer   |单位id   |
|formId   |Integer   |表单id   |
|formAlias   |String   |表单别名   |
|formUserId   |Long   |数据行id   |
|uname   |String   |提交人用户名（审批发起人）   |
|formName   |String   |表单名   |
|formData   |List<Field>   |表单数据字段信息   |
|inserttime   |Date   |提交时间（审批发起时间）   |
|updatetime   |Date   |更新时间   |
|title   |String   |审批标题（审批特有）   |
|aprvStatus   |String   |审批状态（审批特有）<br>0-待审批 <br>1-已同意 <br>2-已撤销 <br>3-已撤销   |
|aprvStatusId   |Integer   |审批状态id（审批特有）<br>0-待审批 <br>1-已同意 <br>2-已撤销 <br>3-已撤销   |
|pageLinkUrl   |String   |审批详情页地址（审批特有）   |
|aprvUsers   |List<AprvUser>   |审批人列表（审批特有）   |
|aprvUsersCC   |List<ApiUserInfo>   |抄送人列表（审批特有）   |
|approvalProcess   |List<ApprovalProcessInfo>   |审批流程信息（审批特有）   |
|aprvTypeId   |Integer   |审批类型id，自建审批10000，定制审批非10000（审批特有）   |
|aprvTitle   |String   |审批自定义标题（审批特有）   |

### Field（字段信息）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|id   |Integer   |组件id   |
|compt   |String   |组件名称   |
|alias   |String   |组件别名   |
|valueList   |List<BaseFieldValue>   |字段值   |
|formDataList   |List<List<Field>>   |子表单内字段   |

### ApprovalProcessInfo（审批流程）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|status   |Integer   |审批节点状态<br> 1-待审批<br> 2-已同意(打回修改节点为已提交)<br> 3-转他人<br> 5-开始处理<br> 9-已回退<br> -1-已拒绝<br> -2-已撤销<br> -5-已撤回上一节点操作<br> -6-已打回修改     |
|statusName   |String   |审批节点状态名称     |
|finishTime   |Date   |审批节点完成时间     |
|aprvType   |Integer   |审批人类型  <br>1-具体人员  <br>2-指定角色|
|aprvUsers   |List<ApiUserInfo>   |审批人   |
|aprvNodeTitle   |String   |审批节点名称   |
|realAprvUsers   |List<ApiUserInfo>   |实际审批人   |
|multiAprvMode   |Integer   |审批方式  1-会签；2-或签  默认为会签   |
|nodeApproveType   |Integer   |节点审批类型 0-未审批 1-待审批 2-已审批   |

### AprvUser（审批人）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|users   |List<ApiUserInfo>   |当前审批环节的审批人列表   |
|way   |Integer   |多人审批时，审批方式。 1-或签 2-会签   |

### ApiUserInfo（用户信息）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|uid   |Long   |用户uid |
|uname   |String   |用户名   |
|userName   |String   |用户名   |
|realAprvTime   |Date   |实际审批人的审批时间   |
|enc   |String   |enc   |
|roleId   |Integer   |角色id   |
|roleName   |String   |角色名   |
|users   |List<ApiUserInfo>   |角色下的人员   |

### ApiStatisticsInfo（分组汇总统计结果）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|name   |String   |统计字段 |
|value   |Double   |统计结果   |
|type   |String   |统计类型   |

### ApproveType（审批类型）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|formId   |Integer   |审批 id |
|aprvType   |String   |审批类型（应用名）   |

### ApproveNodeInfo（审批节点信息）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|id   |Integer   |审批节点id |
|name   |String   |审批节点名称   |

### AprvUsersCc（审批人）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|uid   |Long   |uid   |
|uname   |String   |姓名   |
|readNotice   |Boolean   |抄送人是否已读   |
