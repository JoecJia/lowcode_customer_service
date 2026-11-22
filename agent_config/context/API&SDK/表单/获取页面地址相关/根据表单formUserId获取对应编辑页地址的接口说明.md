**简要描述：**

- 根据表单formUserId获取对应编辑页地址的接口说明

**请求URL：**
- http://m.oa.chaoxing.com/api/apps/forms/user/edit/url?datetime=&fid=&formId=&formUserId=&sign=&enc=

**请求方式：**
- GET,POST均可

**参数说明：**

|参数名称|是否必填|参数类型|参数名称|参数说明|
|:----    |:----|:----- |:-----   |-----   |
|formId   |是  |int | 表单ID    | |
|formUserId   |是  |int | 表单用户填写id    | 数据表行id|
|fid   |是  |int | 单位ID    |单位fid|
|roleId   |否  |int | 角色ID    |角色ID,若传此参数,则生成的链接中带有roleId|
|fieldPermissions|否|string|字段ID权限 JSON|优先使用，例如 `{"1":0,"2":1}`；最终以 `fieldPermissions` 拼接到编辑地址|
|fieldAliasPermissions|否|string|字段别名权限 JSON|仅在 `fieldPermissions` 为空时使用，别名转字段ID后以 `fieldPermissions` 拼接到编辑地址|
|datetime |是  |string |生成加密串时间   | 格式：yyyyMMddHH|
|sign     |是  |string | 接口标识    | 由超星办公系统方提供|
|enc      |是  |string | 接口参数加密串    |采用md5加密方式进行生成|
|tabId |否  |string |【tabId】 |多标签表单的标签 id；不传无法生成指定标签的编辑链接 |
|successTip |否  |string |【successTip】 |打开编辑页后的提示配置 |
|backurl |否  |string |【backurl】 |编辑完成后的回跳地址 |
|uid |否  |long |【uid】 |目标用户 uid |
|permissionGroupId |否  |int |【permissionGroupId】 |权限组 id |

**返回结果**

（1）成功

* 返回数据格式：
```json
       {
           "data": {
             "formEditUrl": "http://office.chaoxing.com/front/web/apps/forms/fore/preview?formId=50946&formUserId=91652&fid=97253&isFormEditUrl=true&enc=5d05ccd4e2d3f0ca81f014f0a7fbc79a&applyenc=00d8a22aacd02577bb804554d098065f&fidEnc=6b6048c33a8382bd"
           },
           "success": true
       }
```

（2）失败

* 返回数据格式：
```json
       {"msg":"验证失败","success":false}
```
```json
       {"msg":"表单不存在","success":false}
```
```json
       {"msg":"表单记录不存在","success":false}
```

**常见失败返回（msg = 业务码 + 文案）：**

|业务码 / msg|触发条件|
|:---|:---|
|表单id不能为空|未传 formId|
|表单用户填写id不能为空|未传 formUserId|
|单位id不能为空|未传 fid|
|表单不存在|formId 定位不到表单|
|表单记录不存在|formUserId 对应的数据行不存在|
|该表单未配置多标签|传了 tabId 但表单未开启多标签|
|tabId参数错误|tabId 不存在|
|fieldAliasPermissions格式错误|字段别名权限 JSON 非法|
|fieldAliasPermissions包含无效字段别名|别名在该表单中不存在|
|获取表单编辑页地址接口异常|服务端异常|

**接口参数配置**

（1）接口标识
> sign=xxx

（2）加密秘钥
> key=xxx

（3）加密原文字符串
> source="[datetime=2021083110][fid=xxx][formId=xxx][formUserId=xxx][sign=xxx]";

（4） MD5加密操作
> enc=md5(source+[key]);

（5） 结果地址
> http://m.oa.chaoxing.com/api/apps/forms/user/edit/url?datetime=xxx&fid=xxx&formId=xxx&formUserId=xxx&sign=xxx&enc=xxx


**注意事项**
（1）生成enc值的参数名称列表必须通过字母a-z的顺序依次组合

* 例如：[a=1][b=2][c=3][ei=4][ej=5]

（2）生成enc值时如果某个参数的值存在多个，在加密过程中要将这些值通过英文逗号进行组合

* 例如：[a=1,2,3,4,5,6]

（3）`fieldPermissions` 和 `fieldAliasPermissions` 同时传入时优先使用 `fieldPermissions`

（4）调用接口时，实际传入的两个参数都需要参与接口 `enc`；返回的编辑地址只包含最终转换后的 `fieldPermissions`
