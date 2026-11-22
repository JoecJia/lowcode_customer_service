
    
**简要描述：** 

- 根据表单行id（formUserId）去获取对应的数据， 支持一次获取多条行id的数据。 主要是给右侧自定义按钮用

**请求URL：** 
http://m.oa.chaoxing.com/api/apps/forms/user/data/list?deptId=&formId=&appName=&formUserIds=&returnFields=&datetime=&sign=&enc=
  
**请求方式：**
- POST
注:因enc参数的校验规则,POST请求支持Content-Type为application/x-www-form-urlencoded,不支持Content-Type为applcation/json

**参数：** 

|参数名|必选|类型|说明|
|:----    |:---|:----- |-----   |
|deptId   |是  |int | 单位fid|
|formId   |否  |int | 表单ID,与appName参数至少要有一个有值 |
|appName   |否  |String | 表单接口标识（别名）,与formId参数至少要有一个有值   |
|formUserIds   |是  |string | 表单行id。 "1,2,3,4"  |
|returnFields |否  |string | 指定需要返回的表单字段 比如需要返回组件别名为name的字段和子表单下组件别名为name1的字段格式为:```[{"alias":"name"},{"alias":"detailbox","subFields":[{"alias":"name1"}]}]```|
|datetime |是  |string |生成加密串时间   格式：yyyyMMddHH|
|sign     |是  |string | 接口标识     由超星办公系统方提供|
|enc      |是  |string | 接口参数加密串    采用md5加密方式进行生成|

 **返回示例**

```
{
    "data": {
        "formUserList": [
            {
                "fid": 1385,
				"formId": 2712,
                "formName": "test",
				 appName:"info",
                "formUserId": 9826,
                "inserttime": 1598264074000,
                "uid": 47101001,
                "uname": "申东杰",
                "updatetime": 1598264074000,
                "formData": [
                    {
                        "compt": "slider",
						"alias":"",
                        "id": 1,
                        "label": "滑动条",
                        "values": [
                            {
                                "val": "99"
                            }
                        ]
                    },
                    {
                        "compt": "multipleselect",
						"alias":"",
                        "id": 2,
                        "label": "多级下拉",
                        "values": [
                            {
                                "val": "a"
                            }
                        ]
                    },
                    {
                        "compt": "editinput",
						"alias":"",
                        "id": 3,
                        "label": "单行输入",
                        "values": [
                            {
                                "val": "单行输入新增"
                            }
                        ]
                    },
                    {
                        "compt": "edittextarea",
						"alias":"",
                        "id": 4,
                        "label": "多行输入",
                        "values": [
                            {
                                "val": "多行输入新增"
                            }
                        ]
                    },
                    {
                        "compt": "numberinput",
						"alias":"",
                        "id": 5,
                        "label": "数字输入框",
                        "values": [
                            {
                                "val": "111"
                            }
                        ]
                    },
                    {
                        "compt": "radiobutton",
						"alias":"",
                        "id": 6,
                        "label": "单选框",
                        "values": [
                            {
                                "val": "a"
                            }
                        ]
                    },
                    {
                        "compt": "checklist",
						"alias":"",
                        "id": 7,
                        "label": "多选框",
                        "values": [
                            {
                                "val": "c"
                            },
                            {
                                "val": "a"
                            }
                        ]
                    },
                    {
                        "compt": "dateinput",
						"alias":"",
                        "id": 8,
                        "label": "日期",
                        "values": [
                            {
                                "val": "2020-08-18 14:30"
                            }
                        ]
                    },
                    {
                        "compt": "datetimerange",
						"alias":"",
                        "id": 9,
                        "label": "开始时间",
                        "values": [
                            {
                                "val": "2020-08-18 14:30"
                            }
                        ]
                    },
					 {
                        "compt": "datetimerange",
						"alias":"",
                        "id": 9,
                        "label": "结束时间",
                        "values": [
                            {
                                "val": "2020-08-30 14:30"
                            }
                        ]
                    },
					 {//若日期区间开启了时长，会返回此字段
                        "compt": "datetimerange",
						"alias":"",
                        "id": 9,
                        "label": "时长",
                        "values": [
                            {
                                "val": "2"
                            }
                        ]
                    },
                    {
                        "compt": "contact",
						"alias":"",
                        "id": 10,
                        "label": "联系人",
                        "values": [
                            {
                                "puid": 47101001,
                                "uname": "申东杰"
                            },
                            {
                                "puid": 47101001,
                                "uname": "申东杰"
                            }
                        ]
                    },
                    {
                        "compt": "department",
						"alias":"",
                        "id": 11,
                        "label": "部门",
                        "values": [
                            {
                                "departmentName": "办公产品部（孟亚飞）",
                                "departmentId": 370411
                            },
                            {
                                "departmentName": "大数据部（杨健）",
                                "departmentId": 391018
                            }
                        ]
                    },
                    {
                        "compt": "selectbox",
						"alias":"",
                        "id": 12,
                        "label": "下拉框",
                        "values": [
                            {
                                "val": "选项1"
                            }
                        ]
                    },
                    {
                        "compt": "selectmultibox",
						"alias":"",
                        "id": 13,
                        "label": "下拉复选框",
                        "values": [
                            {
                                "val": "选项2"
                            }
                        ]
                    },
                    {
                        "compt": "slider",
						"alias":"",
                        "id": 15,
                        "label": "滑动条",
                        "values": [
                            {
                                "val": "88"
                            }
                        ]
                    }
                ]
            }
        ]
    },
    "success": true
}
```

 **返回参数说明** 

|参数名|类型|说明|
|:-----  |:-----|-----                           |
|fid |int   |提交者单位id  |
|uid |int   |提交者uid  |
|uname |int   |提交者用户名  |
|formId |int   |表单id  |
|appName |String   |表单接口标识(别名)  |
|formUserId |long   |表单记录填写id  |
|aprvStatus |int |数据审核状态 null:表单未开启审核 0:待审核 1:通过 2:拒绝|
|auditRemark|string|审核不通过原因|
|auditTime |Date|审核时间|
|aprvAppId |int   |审批模板id  |
|formData |String   |用户提交表单数据  |
|updatetime |Date   |更新时间  |
|inserttime |Date   |提交时间  |

###接口参数配置(sign,key由超星办公系统方分配)
（1）接口标识
> sign=xxxxxx

（2）加密秘钥
> key=xxxxxxx

（3）加密原文字符串  
```
> source="[appName=info][datetime=2020090916][deptId=1385][formId=2712][formUserIds=9826,9843][returnFields=][sign=xxxxxx]";
```
          
（4） MD5加密操作
> enc=md5(source+[key]);
          
（5） 结果地址
> http://m.oa.chaoxing.com/api/apps/forms/user/data/list?appName=info&formId=2712&datetime=2020090916&deptId=1385&sign=xxxxxx&enc=2472007ceabf08b99f06b867e98c090d&formUserIds=9826%2C9843&returnFields=
                 
### 注意事项
（1）生成enc值的参数名称列表必须通过字母a-z的顺序依次组合

* 例如：[a=1][b=2][c=3][ei=4][ej=5]
  
（2）生成enc值时如果某个参数的值存在多个，在加密过程中要将这些值通过英文逗号进行组合

* 例如：[a=1,2,3,4,5,6]
