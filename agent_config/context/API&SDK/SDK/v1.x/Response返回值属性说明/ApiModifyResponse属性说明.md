
[TOC]

# 表单/审批 增删改相关接口返回值对象
### ApiModifyResponse

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|code   |String   |状态码（详情请见[状态码说明](https://cxapi.chaoxing.com/web/#/653656294/207980774 "状态码说明")）   |
|success   |Boolean   |成功标识   |
|msg   |String   |接口返回的信息   |
|data   |ApiModifyResponseData   |接口返回的数据   |

### ApiModifyResponseData（返回值数据）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|succeedList   |List<SuccessFailedInfo>   |成功信息集合   |
|failedList   |List<SuccessFailedInfo>   |失败信息集合   |
|formUserId   |Long   |数据行id   |
|detailUrl   |String   |详情页url   |
|noticeIdList   |List<Integer>   |通知id集合   |
|repeatFormUserId   |Long   |唯一值校验失败后，与当前数据所重复的formUserId   |
|extraParam   |String   |调接口时传的extraParam额外参数，在接口成功时原样返回   |
|totalCount   |Integer   |删除接口返回本次执行删除时的数据量（SDK v1.19.5 起支持）   |

### SuccessFailedInfo（成功失败信息）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|formUserId   |Long   |数据行id   |
|msg   |String   |错误信息   |
|dataIndex   |Integer   |数据下标   |
|repeatFormUserId   |Long   |唯一值校验失败后，与当前数据所重复的formUserId   |
|detailUrl   |String   |详情页url（SDK v1.23.3 起支持）   |
|updatetime   |Date   |数据更新时间（SDK v1.16.1 起支持）   |
|formData   |List<Field>   |成功后返回的表单数据字段信息（SDK v1.16.1 起支持）   |

