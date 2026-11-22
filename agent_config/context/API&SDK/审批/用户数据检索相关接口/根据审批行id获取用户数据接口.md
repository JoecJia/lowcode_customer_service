
    
**简要描述：** 

- 根据表单行id（formUserId）去获取对应的数据， 支持一次获取多条行id的数据

**请求URL：** 
http://m.oa.chaoxing.com/api/approve/forms/user/data/list?deptId=&formId=&appName=&formUserIds=&returnFields=&datetime=&sign=&enc=
  
**请求方式：**
- POST 

**参数：** 

|参数名|必选|类型|说明|
|:----    |:---|:----- |-----   |
|deptId   |是  |int | 单位fid|
|formId   |否  |int | 表单ID  |
|appName  |否  |String | 表单接口标识（别名)  |
|formUserIds   |是  |string | 表单行id,多个行id以逗号分隔 "1,2,3,4"  |
|returnFields |否  |string | 指定需要返回的表单字段 比如需要返回组件别名为name的字段和子表单下组件别名为name1的字段格式为:[{"alias":"name"},{"alias":"detailbox","subFields":[{"alias":"name1"}]}]|
|datetime |是  |string |生成加密串时间   格式：yyyyMMddHH|
|sign     |是  |string | 接口标识     由超星办公系统方提供|
|enc      |是  |string | 接口参数加密串    采用md5加密方式进行生成|
|aprvTypeId |否 |int |审批类型 id，默认 10000 |

**返回参数说明：**

| 参数名              | 类型     | 说明         |
|:-----------------|:-------|------------|
| fid              | int    | 提交者单位id    |
| uid              | int    | 提交者uid     |
| uname            | int    | 提交者用户名     |
| formId           | int    | 表单id       |
| appName          | String | 表单接口标识（别名) |
| formName         | String | 表单应用名称     |
| title            | String | 审批标题       |
| formUserId       | int    | 表单记录填写id   |
| aprvAppId        | int    | 审批模板id     |
| formData         | String | 用户提交表单数据   |
| aprvStatusTypeId | int    | 审批状态id(参照下方说明)  |
| aprvStatusType   | String | 审批状态(参照下方说明)  |
| version          | int    | 表单版本号      |
| updatetime       | Date   | 更新时间       |
| inserttime       | Date   | 提交时间       |
| ApprovalProcess  | List   | 审批流程信息     |


**ApprovalProcess参数说明：**

| 参数名称           | 参数类型     | 参数说明                                                                         |
|:---------------|:---------|------------------------------------------------------------------------------|
| status            | Integer   | 审批节点状态 1-待审批 2-已同意(打回修改节点为已提交) 3-转他人 5-开始处理 9-已回退 -1-已拒绝 -2-已撤销 -5-已撤回上一节点操作 -6-已打回修改 |
| statusName        | String     | 审批节点状态名称                                                                     |
| finishTime        | Date     | 审批节点完成时间                                                                     |
| aprvType        | Integer     | 审批人类型1-具体人员2-指定角色                                                            |
| aprvUsers      | List        | 审批人                                                                          |
| aprvNodeTitle  | String    | 审批节点名称                                                                       |
| realAprvUsers  | List        | 实际审批人                                                                        |
| multiAprvMode  | Integer  | 审批方式1-会签；2-或签 默认为会签                                                          |

**aprvUsers参数说明：**

| 参数名称      | 参数类型     | 参数说明   |
|:----------|:---------|--------|
| uid         | Long       | 用户uid  |
| userName   | String    | 用户名    |
| roleId       | Integer    | 角色id   |
| roleName   | String    | 角色名    |
| users     | List     | 角色下的人员 |

**realAprvUsers参数说明：**

| 参数名称                 | 参数类型    | 参数说明       |
|:---------------------|:--------|------------|
| uid                    | Long       | 用户uid      |
| userName              | String    | 用户名        |
| realAprvTime          | Date    | 实际审批人的审批时间 |
| signature            | String     | 手写签名图片地址   |
| electronicSignature    | String   | 电子签章图片地址   |
| file                  | String    | 审批意见文件     |
| picture                | String   | 审批意见图片     |
| opinion                | String   | 审批意见       |

 **返回示例**

```
{
  "data": {
    "formUserList": [
      {
        "ApprovalProcess": [
          {
            "aprvUsers": [
              {
                "uid": 53149614,
                "userName": "用户1"
              }
            ],
            "finishTime": 1740057544000,
            "aprvType": 1,
            "aprvNodeTitle": "审批人1",
            "statusName": "同意",
            "realAprvUsers": [
              {
                "realAprvTime": 1740057544000,
                "uid": 53149614,
                "file": "[]",
                "signature": "http://pan-yz.chaoxing.com/thumbnail/origin/ba229daa3680172615a0fd4ff98cc32a",
                "electronicSignature": "http://pan-yz.chaoxing.com/thumbnail/origin/6c7d786936dbe5dd86f17f14746a0f1e",
                "userName": "用户1",
                "picture": "[]",
                "opinion": "审批意见"
              }
            ],
            "multiAprvMode": 1,
            "status": 2
          },
          {
            "aprvUsers": [
              {
                "roleId": 58803,
                "roleName": "角色1",
                "users": [
                  {
                    "uid": 234113304,
                    "userName": "用户2"
                  }
                ]
              }
            ],
            "finishTime": 1740057579000,
            "aprvType": 2,
            "aprvNodeTitle": "审批人2",
            "statusName": "处理完成",
            "realAprvUsers": [
              {
                "realAprvTime": 1740057573000,
                "uid": 234113304,
                "file": "[{\"objectId\":\"5a2363a46e3fe3a3bb010b440fc5e9ec\",\"fileUrl\":\"http://pan-yz.chaoxing.com/thumbnail/origin/5a2363a46e3fe3a3bb010b440fc5e9ec?type=document\",\"name\":\"017.pdf\",\"suffix\":\"pdf\",\"size\":\"137.14KB\",\"puid\":378677113,\"resid\":\"1099439484845674496\",\"byteSize\":140432}]",
                "signature": "https://pan-yz.chaoxing.com/thumbnail/origin/b34996f2c663c45c867006778bfc6d98",
                "electronicSignature": "http://pan-yz.chaoxing.com/thumbnail/origin/bd611758eb3482064fc95236fbb5b48d",
                "userName": "用户2",
                "picture": "[{\"objectId\":\"eb88db96bc6e18fd5bb5e6666b5abe16\",\"fileUrl\":\"http://pan-yz.chaoxing.com/thumbnail/origin/eb88db96bc6e18fd5bb5e6666b5abe16?type=img\",\"name\":\"u=1824494157,3969999074&fm=253&app=138&f=JPEG.jpg\",\"suffix\":\"jpg\",\"size\":\"90.8KB\",\"puid\":378677113,\"resid\":\"1099439403459399680\",\"byteSize\":92977}]",
                "opinion": "审批意见"
              },
              {
                "realAprvTime": 1740057579000,
                "uid": 234113304,
                "file": "[]",
                "signature": "https://pan-yz.chaoxing.com/thumbnail/origin/b34996f2c663c45c867006778bfc6d98",
                "electronicSignature": "http://pan-yz.chaoxing.com/thumbnail/origin/bd611758eb3482064fc95236fbb5b48d",
                "userName": "用户2",
                "picture": "[]",
                "opinion": "审批意见"
              }
            ],
            "multiAprvMode": 2,
            "status": 2
          }
        ],
        "appName": "10002",
        "aprvAppId": 10002,
        "aprvStatusType": "已同意",
        "aprvStatusTypeId": 2,
        "fid": 1385,
        "formData": [
          {
            "compt": "editinput",
            "label": "单行输入",
            "values": [
              {
                "val": "432"
              }
            ]
          },
          {
            "compt": "edittextarea",
            "label": "多行输入",
            "values": [
              {
                "val": ""
              }
            ]
          },
          {
            "compt": "radiobutton",
            "label": "选择",
            "values": [
              {
                "val": ""
              }
            ]
          },
          {
            "compt": "checklist",
            "label": "选择",
            "values": [
              {
                "val": ""
              }
            ]
          },
          {
            "compt": "dateinput",
            "label": "日期",
            "values": [
              {
                "val": ""
              }
            ]
          },
          {
            "compt": "datetimerange",
            "label": "开始时间",
            "values": [
              {
                "val": "2020-09-01 00:00"
              }
            ]
          },
          {
            "compt": "numberinput",
            "label": "出差车费",
            "values": [
              {
                "val": ""
              }
            ]
          },
          {
            "compt": "numberinput",
            "label": "住宿费",
            "values": [
              {
                "val": ""
              }
            ]
          },
          {
            "compt": "imagebox",
            "label": "图片",
            "values": [
              {
                "modifyDate": 1598924129116,
                "size": "18.0KB",
                "name": "170131709880.jpg",
                "fileUrl": "http://pan-yz.chaoxing.com/thumbnail/origin/c90ecd78062e4a2208a38d80d8da7d29",
                "suffix": "jpg",
                "objectId": "c90ecd78062e4a2208a38d80d8da7d29"
              }
            ]
          },
          {
            "compt": "fileupload",
            "label": "附件",
            "values": [
              {
                "modifyDate": 1598924133674,
                "size": "19.7KB",
                "name": "1462590059175.jpg",
                "suffix": "jpg",
                "objectId": "aeac21440eca8583206124f30bfca7df"
              }
            ]
          },
          {
            "compt": "datetimerange",
            "label": "开始时间",
            "values": [
              {
                "val": ""
              }
            ]
          },
          {
            "compt": "numberinput",
            "label": "数字输入框",
            "values": [
              {
                "val": "432"
              }
            ]
          }
        ],
        "formId": 10002,
        "formName": "审批表单",
        "formUserId": 519,
        "inserttime": 1598924155000,
        "isDelete": "用户3的审批表单",
        "uid": 21662618,
        "uname": "用户3",
        "updatetime": 1598924155000,
        "version": 15
      }
    ]
  },
  "success": true
}
```

**常见失败返回（msg = 业务码 + 文案）：**

|业务码 / msg|触发条件|
|:---|:---|
|表单id和表单别名不能同时为空|formId 与 appName 均未传|
|单位id不能为空|未传 deptId|
|行id不能为空|未传 formUserIds|
|审批不存在|formId / appName 定位不到审批|
|根据行id获取用户数据列表异常|服务端处理异常|

###接口参数配置(sign,key由超星办公系统方分配)
（1）接口标识
> sign=approveData_xxx

（2）加密秘钥
> key=xxx

（3）加密原文字符串  
```
> source="[appName=info][datetime=2020090916][deptId=1385][formId=10002][formUserIds=519,520][returnFields=][sign=xxx]";
```          
（4） MD5加密操作
> enc=md5(source+[key]);
          
（5） 结果地址
> http://m.oa.chaoxing.com/api/approve/forms/user/data/list?formId=10002&appName=info&datetime=2020090916&deptId=1385&sign=xxx&enc=d944c1261d34e0523d0191bb6a825ecd&formUserIds=519%2C520&returnFields=
                 
### 注意事项
（1）生成enc值的参数名称列表必须通过字母a-z的顺序依次组合

* 例如：[a=1][b=2][c=3][ei=4][ej=5]
  
（2）生成enc值时如果某个参数的值存在多个，在加密过程中要将这些值通过英文逗号进行组合

* 例如：[a=1,2,3,4,5,6]
