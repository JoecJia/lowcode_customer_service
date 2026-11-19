
[TOC]

# 表单/审批 检索相关接口
### ApiNodeConfigResponse

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|code   |String   |状态码（详情请见[状态码说明](https://cxapi.chaoxing.com/web/#/653656294/207980774 "状态码说明")）   |
|success   |Boolean   |成功标识（true / false）   |
|msg   |String   |接口返回的信息   |
|data   |ApiNodeConfigResponseData   |接口返回的数据   |

### ApiNodeConfigResponseData

|属性   |类型   |备注   |
| ------------ | ------------ | ------------ |
|buttonConfig   |String   |节点审批按钮配置   |
|formAuthority   |String   |节点权限   |
