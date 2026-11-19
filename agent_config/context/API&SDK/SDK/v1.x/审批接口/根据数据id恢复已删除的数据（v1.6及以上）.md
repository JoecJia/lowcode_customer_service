
[TOC]
    
##### 简要描述

- 根据数据id恢复已删除的数据（v1.6及以上）

##### 方法调用
- ` OfficeApproveApiInvokeService.batchRecoveryApproveData `

##### 返回值类型
- [ApiModifyResponse](https://cxapi.chaoxing.com/web/#/653656294/207980778 "ApiModifyResponse")（详情请点击跳转）

##### 参数

|参数名|必填|类型|说明|
|:----    |:---|:----- |----- |
|fid |是  |Integer |【单位ID】   |
|formId |是  |Integer | 【表单ID】（formId和formAlias任选一个）    |
|formAlias |是  |String | 【表单别名】表单接口标识（formId和formAlias任选一个）   |
|formUserIds |是  |String | 【检索条件】 需要更新的数据行id。多值格式”1,2,3,4”,以逗号分隔，每次最多50条    |
|operatorUid |是  |Long | 【操作人uid】用于记录此次恢复的操作人    |
|autoSendData |否  |Integer | 【数据推送】默认为1可触发数据推送，0:不触发数据推送    |

##### 调用示例（仅供参考）

```java
public void testBatchRecovery() {
	//调sdk接口
	ApiModifyResponse batchRecoveryByFormUserId = OfficeApproveApiInvokeService.recoveryApproveUserDataByFormUserId(fid,
																												    938716,
																												    "938716"
																												    "636150833,636150830,636150292",
																												    111111,
																												    PushDataEnum.TRUE.type);
}
```

##### 返回示例 

```
{
  "code": "200",
  "success": true,
  "msg": "批量恢复成功1条",
  "data": {
    "failedList": [
      {
        "msg": "该数据非删除状态",
        "formUserId": 636150830
      },
	  {
        "msg": "该数据不存在或已被彻底删除",
        "formUserId": 636150292
      }
    ]
  }
}
```





