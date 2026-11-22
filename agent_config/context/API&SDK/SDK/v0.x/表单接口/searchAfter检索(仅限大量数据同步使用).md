
[TOC]
    
##### 简要描述

- searchAfter检索接口(仅限大量数据同步使用)

##### 方法调用
- ` OfficeApiInvokeService.formUserSearchAfterListByFormId `

- ` OfficeApiInvokeService.formUserSearchAfterListByAlias `

##### 返回值类型
- [ApiResponse](https://cxapi.chaoxing.com/web/#/653656294/207981362 "ApiResponse")（详情请点击跳转）

##### 参数

|参数名|必填|类型|说明|
|:----    |:---|:----- |-----   |
|fid |是  |Integer |【单位ID】   |
|formId |是  |Integer | 【表单ID】（formId和formAlias任选一个）    |
|formAlias |是  |String | 【表单别名】表单接口标识（formId和formAlias任选一个）   |
|uid |否  |Integer | 【提交人uid】    |
|formUserId |否  |Integer | 【表单记录id】表单用户填写id    |
|sortValues |否  |String | 【游标】search_after检索方式特有参数，上一次请求数据返回游标，用于下一次请求    |
|limit |否  |Integer | 【每页条数】默认30条，最多1次限制100条    |
|orderType |否  |String | 【排序类型】按照表单用户填写时间排序（desc降序，asc升序，默认desc）    |
|returnFields |否  |String | 【指定需要返回的表单字段】 比如需要返回组件别名为name的字段和子表单下组件别名为name1的字段格式为:[{“alias”:”name”},{“alias”:”detailbox”,”subFields”:[{“alias”:”name1”}]}]    |
|startTime |否  |String | 【检索条件】数据插入时间--开始时间，参数格式 yyyy-MM-dd HH:mm:ss    |
|endTime |否  |String | 【检索条件】数据插入时间--结束时间，参数格式 yyyy-MM-dd HH:mm:ss    |

##### 返回示例 

```
{
  "code": "200",
  "success": true,
  "msg": "请求成功",
  "data": {
    "total": 2,
    "sortValues": "3fcf2e2bb2f73306a85711575cb61fa4",
    "dataList": [
      {
        "uid": 66666666,
        "fid": 100,
        "formId": 100,
        "formAlias": "100",
        "formUserId": 100,
        "uname": "xxx",
        "formName": "测试",
        "formData": [
          {
            "id": 1,
            "compt": "editinput",
            "alias": "1",
            "valueList": [
              {
                "val": "test"
              }
            ]
          },
          {
            "id": 2,
            "compt": "edittextarea",
            "alias": "2",
            "valueList": [
              {
                "val": "test"
              }
            ]
          }
        ],
        "inserttime": 1670208301318,
        "updatetime": 1670208301318
      }
    ]
  }
}
```





