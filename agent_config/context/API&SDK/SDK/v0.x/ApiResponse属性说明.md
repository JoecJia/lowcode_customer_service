
[TOC]

### ApiResponse

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|code   |String   |状态码   |
|success   |Boolean   |成功标识   |
|msg   |String   |接口返回的信息   |
|data   |ResultData   |接口返回的数据   |

### ResultData（返回值数据）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|total   |Integer   |总条数   |
|totalPage   |Integer   |总页数   |
|formUserId   |Long   |数据行id   |
|sortValues   |String   |接口返回的数据   |
|dataList   |List<FormsUser>   |表单数据集合   |
|succeedList   |List<SuccessFailedInfo>   |成功信息集合   |
|failedList   |List<SuccessFailedInfo>   |失败信息集合   |

### SuccessFailedInfo（成功失败信息）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|formUserId   |Long   |数据行id   |
|msg   |String   |错误信息   |
|dataIndex   |Integer   |数据下标   |

### FormsUser（表单记录）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|uid   |Integer   |用户uid   |
|fid   |Integer   |单位id   |
|formId   |Integer   |表单id   |
|formAlias   |String   |表单别名   |
|formUserId   |Integer   |数据行id   |
|uname   |String   |用户名   |
|formName   |String   |表单名   |
|formData   |List<Field>   |表单数据字段信息   |
|inserttime   |Date   |提交时间   |
|updatetime   |Date   |更新时间   |

### Field（字段信息）

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|id   |Integer   |组件id   |
|compt   |String   |组件名称   |
|alias   |String   |组件别名   |
|valueList   |List<BaseFieldValue>   |字段值   |
|formDataList   |List<List<Field>>   |子表单内字段   |


