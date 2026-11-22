
[TOC]

# 表单/审批 检索相关接口
### ApiApproveFlowResponse

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|code   |String   |状态码（详情请见[状态码说明](https://cxapi.chaoxing.com/web/#/653656294/207980774 "状态码说明")）   |
|success   |Boolean   |成功标识（true / false）   |
|msg   |String   |接口返回的信息   |
|data   |ApiApproveFlowResponseData   |接口返回的数据   |

### ApiApproveFlowResponseData

|参数名|类型|说明|
|:-----           |:-----     |-----   |
|statusTypeId     |Integer |审批状态ID值，0-待审批，1-已同意，2-已拒绝，3-已撤回(审批中)， 4- 已撤销（审批已通过后）|
|statusTypeName   |String  |审批状态文本值， 取值：待审批、已通过、已拒绝、已撤回、已撤销|
|applicationUid   |Long |发起人uid|
|applicationUname |String  |发起人uname|
|approveUserList  |List<ApproveNodeDetailInfo> |审批流节点数组，详情参考下面说明|
|insertTime	      |Date  |审批发起时间， 时间戳格式|
|updateTime	      |Date  |审批完成时间， 时间戳格式|

### ApproveNodeDetailInfo

|参数名|类型|说明|
|:-----           |:-----    |-----   |
|title            |String    |当前审批节点名称|
|explain          |String    |节点说明，例如“多人或签”、“辅导员角色会签”|
|cardType         |Integer   |节点类型 1: 审批人 2:抄送人 |
|model            |Integer   |审批模式 1:单人模式 2:多人模式 |
|statusTypeId     |Integer   |节点审批状态。0-未审批（多人或签，自己没有审批） 1-待审批 2-已同意/已提交 3-转他人 5-开始处理 9-已回退 -1-已拒绝 -2-已撤销 -5-已撤回上一节点操作 -6-已打回修改|
|statusTypeName   |String    |节点审批状态文本值。 取值：未审批， 待审批， 已同意， 转他人， 开始处理， 已回退， 已拒绝， 已撤销， 已撤回上一节点操作， 已打回修改， 已提交|
|id               |Long       |审批人uid/角色id。 当model=2，同时children为空或者不存在，该参数的值为角色id，否则为用户uid |
|handleTime       |Date      |审批时间， 时间戳格式(抄送节点代表抄送时间) |
|children         |List<ApproveNodeDetailInfo>     |当model=2时，该参数有值。 如果是多人审批，数组里是具体人员列表；如果是角色审批，数组里是角色列表。 数组里对象结构同approveUserList数组对象|
|backModifyNode   |Integer   |打回修改节点标识 |
|opinion          |String    |处理意见 |
|file             |String    |文件(处理意见中添加的附件) |
|picture          |String    |图片(处理意见中添加的图片) |
|sign             |String    |手写签名 |
|electronicSign   |String    |电子签章 |
|nodeUniqueId     |Long      |节点唯一id |
|lastNodeUniqueIdList     |List<Long>      |上一级节点唯一id列表 |
|nextNodeUniqueIdList     |List<Long>      |下一级节点唯一id列表 |
