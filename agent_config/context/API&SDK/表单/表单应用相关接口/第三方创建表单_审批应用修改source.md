**简要描述：**

- 第三方表单/审批修改source来源接口（使用sign需要与创建表单创建表单使用deptManager_*类型sign做绑定，否则无权限修改）

**请求URL：**
- http://m.oa.chaoxing.com/api/apps/forms/app/edit/source?fid=&sign=&formId=&formType=&operatorUid=&enc=

**请求方式：**
- GET,POST均可

**参数说明：**

|参数名称| 是否必填 | 参数类型   | 参数名称    | 参数说明                           |
|:----    |:-----|:-------|:--------|--------------------------------|
|datetime | 是    | string | 生成加密串时间 | 格式：yyyyMMddHH                  |
|sign     | 是    | string | 接口标识    | 由超星办公系统方提供                     |
|enc      | 是    | string | 接口参数加密串 | 采用md5加密方式进行生成                  |
|fid   | 是    | int    | 单位ID    | 单位fid                          |
|formId   | 否    | int    | 表单ID    | 表单id                           |
|appName   | 否    | string | 接口标识    | 接口标识                           |
|formType   | 否    | int    | 应用类型    | 应用类型，默认值为2；1.表示自建审批；2.表示自定义表单; |
|operatorUid   | 是    | int    | 操作人ID   | 操作人ID |


**返回结果**
（1）成功

* 返回数据格式：
```json
{
  "success": true,
  "msg": "更新成功"
}
```
（2）失败

* 返回数据格式：
```json
{
  "success": false,
  "msg": "更新失败"
}
```

**补充说明：**

|项|说明|
|:---|:---|
|目标 source|接口没有“目标来源”入参；实现把 `source` 改成 `sign` 命中记录的 `api_third_config.id`，目标来源完全由 `sign` 决定|

**常见失败返回（msg = 业务码 + 文案）：**

|业务码 / msg|触发条件|
|:---|:---|
|单位id不能为空|未传 fid|
|操作人uid不能为空|未传 operatorUid|
|应用id和表单别名不能同时为空|formId 与 appName 同时为空|
|授权sign不能为空|未传 sign|
|formType参数不合法|formType 不是 1/2|
|授权sign不正确|sign 未登记|
|无权限修改|sign 未与创建时的 deptManager_* 绑定|

**接口参数配置**
（1）接口标识类型
> sign= appsFormsData_*

（2）加密秘钥
> key=xxx

（3）加密原文字符串
> source="[datetime=2025091714][fid=63555][formId=111][formType=2][sign=xxx]";
          
（4） MD5加密操作
> enc=md5(source+[key]);
          
（5） 结果地址
> http://m.oa.chaoxing.com/api/apps/forms/app/edit/source?fid=63555&formId=111&datetime=2025091714&formType=2&sign=xxx&enc=69b7eaa1677f87a63c77cc9877e1a5b5


**注意事项**
（1）生成enc值的参数名称列表必须通过字母a-z的顺序依次组合

* 例如：[a=1][b=2][c=3][ei=4][ej=5]
  
（2）生成enc值时如果某个参数的值存在多个，在加密过程中要将这些值通过英文逗号进行组合

* 例如：[a=1,2,3,4,5,6]
