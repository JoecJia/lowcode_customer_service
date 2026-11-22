

[TOC]
    
##### 简要描述

- 根据审批行id获取用户数据接口

##### 方法调用
- ` OfficeApproveApiInvokeService.getApproveUserDataListByFormId `

- ` OfficeApproveApiInvokeService.getApproveUserDataListByAlias `

##### 返回值类型
- [ApiSearchResponse](https://cxapi.chaoxing.com/web/#/653656294/207980779 "ApiSearchResponse")（详情请点击跳转）

##### 参数

|参数名|必填|类型|说明|
|:----    |:---|:----- |-----   |
|fid |是  |Integer |【单位ID】   |
|formId |否  |Integer | 【表单ID】（formId和formAlias任选一个）    |
|formAlias |否  |String | 【表单别名】表单接口标识（formId和formAlias任选一个）   |
|formUserIds |是  |String | 【审批记录ID】审批用户填写记录id，多个行id以逗号分隔 "1,2,3,4"    |
|returnFields |否  |String | 【指定需要返回的表单字段】 比如需要返回组件别名为name的字段和子表单下组件别名为name1的字段格式为:[{“alias”:”name”},{“alias”:”detailbox”,”subFields”:[{“alias”:”name1”}]}]    |

##### 调用示例（仅供参考）

```java
ApiSearchResponse userDataList = OfficeApproveApiInvokeService.getApproveUserDataListByFormId(fid,
																							  15496,
																							  "4964907,4964904,4964900",
																							  "[{\"alias\":\"name\"}]");
```

##### 返回示例 

```
{
  "code": "200",
  "success": true,
  "msg": "请求成功",
  "data": {
    "dataList": [
      {
        "uid": 58178393,
        "fid": 170507,
        "formId": 15496,
        "formAlias": "15496",
        "formUserId": 4965494,
        "uname": "任鑫意",
        "formName": "审批sdk测试",
        "formData": [
          {
            "id": 1,
            "compt": "editinput",
            "alias": "1",
            "valueList": [
              {
                "val": "单行输入test"
              }
            ]
          }
        ],
        "inserttime": 1680747162393,
        "updatetime": 1680761291115,
        "title": "任鑫意的审批sdk测试",
        "aprvStatus": "已通过",
        "aprvStatusId": 1,
        "pageLinkUrl": "http://t.chaoxing.com/front/approve/apps/forms/fore/detail/approve?formId=15496&id=4965494&pageEnc=5d056abffdb945bf7fda4c457d61a2a9&fidEnc=18e34e3a7cd3b285",
        "aprvUsers": [
          {
            "users": [
              {
                "uid": 58178393,
                "uname": "任鑫意",
                "enc": "4d1db55c9756a46a7885911883e3a0b1"
              }
            ],
            "way": 2
          },
          {
            "users": [
              {
                "uid": 58178393,
                "uname": "任鑫意",
                "enc": "4d1db55c9756a46a7885911883e3a0b1",
                "roleId": 217
              },
              {
                "uid": 195817262,
                "uname": "发啊撒旦",
                "enc": "238e137e11dd8d44b9526a3ee6a994e0",
                "roleId": 217
              }
            ],
            "way": 1
          }
        ],
        "aprvUsersCC": [
          {
            "uid": 195817262,
            "uname": "发啊撒旦",
            "enc": "238e137e11dd8d44b9526a3ee6a994e0"
          }
        ],
        "ApprovalProcess": [
          {
            "aprvUsers": [
              {
                "uid": 58178393,
                "userName": "任鑫意"
              }
            ],
            "aprvType": 1,
            "aprvNodeTitle": "审批人",
            "realAprvUsers": [
              {
                "uid": 58178393,
                "userName": "任鑫意",
                "realAprvTime": 1680747165000
              }
            ],
            "multiAprvMode": 1,
            "status": 2,
            "statusName": "已处理完成",
            "finishTime": 1683286399000
          },
          {
            "aprvUsers": [
              {
                "roleId": 217,
                "roleName": "超级管理员",
                "users": [
                  {
                    "uid": 58178393,
                    "userName": "任鑫意"
                  },
                  {
                    "uid": 195817262,
                    "userName": "发啊撒旦"
                  }
                ]
              }
            ],
            "aprvType": 1,
            "aprvNodeTitle": "审批人",
            "realAprvUsers": [
              {
                "uid": 58178393,
                "userName": "任鑫意",
                "realAprvTime": 1680747165000
              }
            ],
            "multiAprvMode": 1,
            "status": -6,
            "statusName": "已打回修改到发起人",
            "finishTime": 1683286399000
          }
        ]
      }
    ]
  }
}
```




