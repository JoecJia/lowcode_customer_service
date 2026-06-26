# 表单/审批 - 字段默认值功能清单

---

## 单行输入 (editinput)
通常用来填写文本信息

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 常用公式（`formula`）
   - 2.1. 身份证号提取出生日期
   - 2.2. 身份证号提取性别
   - 2.3. 身份证号提取年龄
   - 2.4. 提取用户uid
   - 2.5. 提取用户学工号
   - 2.6. 提取文件名称
   - 2.7. 提取行政区划码
3. 数据联动（`linkInfo.linked`）
4. 上次填写内容（`latestValShow`）
5. 公式编辑（`formulaEdit.formula`）

**校验支持：**
- 必填（`verify.required`）
- 字符长度限制（`verify.charLimit`）：最大长度/最小长度
- 正则表达式（`verify.regularExpress`）：自定义正则 + 错误提示
- 唯一性检查（`verify.unique`）：不允许重复提交
- 格式校验（`verify.format`）：邮箱、身份证号等特殊格式
- 联想输入（`associativeInput`）：关联表单字段联想 / 自定义联想 / 第三方API联想
- 脱敏（`desensitive` / `desensitiveConfig`）
- 扫码录入（`sweepCode`）

---

## 多行输入 (edittextarea)
通常用来填写较长文本信息，如备注、说明等

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 常用公式（`formula`）
   - 2.1. 身份证号提取出生日期
   - 2.2. 身份证号提取性别
   - 2.3. 身份证号提取年龄
   - 2.4. 提取用户uid
   - 2.5. 提取用户学工号
   - 2.6. 提取文件名称
   - 2.7. 提取行政区划码
3. 数据联动（`linkInfo.linked`）
4. 上次填写内容（`latestValShow`）
5. 公式编辑（`formulaEdit.formula`）

**校验支持：**
- 字符长度限制（`verify.charLimit`）：最大长度/最小长度

---

## 数字输入 (numberinput)
通常用来填写数值类型信息，如金额、数量等

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 常用公式（`formula`）
   - 2.1. 身份证号提取出生日期
   - 2.2. 身份证号提取性别
   - 2.3. 身份证号提取年龄
   - 2.4. 提取用户uid
   - 2.5. 提取用户学工号
   - 2.6. 提取文件名称
   - 2.7. 提取行政区划码
3. 数据联动（`linkInfo.linked`）
4. 上次填写内容（`latestValShow`）
5. 公式编辑（`formulaEdit.formula`）

**校验支持：**
- 最小值（`verify.minValue`）
- 最大值（`verify.maxValue`）
- 数字精度（`verify.realNumber`）：整数/小数、小数位数、保留位数
- 格式校验（`verify.format`）
- 千分符显示（`micrometer`）
- 中文大写（`capital`）
- 百分比显示（`percentage`）
- 计数器输入模式（`step`）

---

## 日期 (dateinput)
用于选择单个日期或日期时间

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 数据联动（`linkInfo.linked`）
3. 上次填写内容（`latestValShow`）
4. 公式编辑（`formulaEdit.formula`）
5. 指定日期（`appoint`） / 更新日期（`updateAppoint`）

**校验支持：**
- 日期合法区间（`verify.validateRange`）：固定日期范围 / 动态日期范围（当天/之前/之后）

---

## 日期区间 (datetimerange)
用于选择开始时间和结束时间，常用于请假、外出等场景

**默认值支持：**
（无独立默认值配置，依赖开始/结束字段各自配置）

**校验支持：**
- 日期区间校验（`verify.dateRange`）：开始时间不能晚于结束时间
- 日期合法区间（`verify.validateRange`）：固定日期范围 / 动态日期范围

---

## 下拉框 (selectbox)
提供下拉选项供用户单选

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 数据联动（`linkInfo.linked`）
3. 默认值数据联动（`defaultLinkInfo`）：单独配置默认值的数据联动来源
4. 上次填写内容（`latestValShow`）
5. 从第三方URL获取选项（`optionsLoadFromUrl`）
6. 关联其他表单选项（`optionBindInfo`）

**校验支持：**
- （无独立校验规则，通过选项限定值范围）
- 选项分值（`optionScoreShow` / `optionScoreUsed`）
- "其他"选项（`otherAllowed` / `openOtherOption`）

---

## 多选 (checklist)
提供多个选项供用户多选

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 上次填写内容（`latestValShow`）

**校验支持：**
- 最少选择数（`verify.minValue`）
- 最多选择数（`verify.maxValue`）

---

## 下拉复选 (selectmultibox)
下拉形式的多选框

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 数据联动（`linkInfo.linked`）
3. 默认值数据联动（`defaultLinkInfo`）
4. 上次填写内容（`latestValShow`）
5. 从第三方URL获取选项（`optionsLoadFromUrl`）
6. 关联其他表单选项（`optionBindInfo`）

**校验支持：**
- 最少选择数（`verify.minValue`）
- 最多选择数（`verify.maxValue`）

---

## 单选 (radiobutton)
平铺单选按钮组

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 上次填写内容（`latestValShow`）

**校验支持：**
- （无独立校验规则）
- 选项分值（`optionScoreShow` / `optionScoreUsed`）
- "其他"选项（`otherAllowed`）

---

## 多级下拉 (multipleselect)
支持树形层级结构的下拉选择，如部门、分类等

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 上次填写内容（`latestValShow`）
3. 从第三方URL获取选项（`optionsLoadFromUrl`）
4. 分类树结构（`typeTree`）

**校验支持：**
- （无独立校验规则）

---

## 图片单选 (imageradiobutton)
以图片形式展示的单选题

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 上次填写内容（`latestValShow`）

**校验支持：**
- （无独立校验规则）

---

## 图片多选 (imagechecklist)
以图片形式展示的多选题

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 上次填写内容（`latestValShow`）

**校验支持：**
- 最少选择数（`verify.minValue`）
- 最多选择数（`verify.maxValue`）

---

## 矩阵单选 (matrixradio)
以矩阵表格形式展示的单选题组

**默认值支持：**
1. 上次填写内容（`latestValShow`）

**校验支持：**
- （无独立校验规则，依赖内部子组件校验）

---

## 矩阵多选 (matrixcheckbox)
以矩阵表格形式展示的多选题组

**默认值支持：**
1. 上次填写内容（`latestValShow`）

**校验支持：**
- （无独立校验规则，依赖内部子组件校验）

---

## 附件 (fileupload)
用于上传文件

**默认值支持：**
1. 数据联动（`linkInfo.linked`）

**校验支持：**
- 最少上传数（`verify.minValue`）
- 最多上传数（`verify.maxValue`）
- 限制文件大小（`verify.limitSize`）
- 限制文件类型（`verify.limitType`）
- 限制上传数量（`verify.limitCount`，旧数据兼容）
- 水印配置（`waterMark`）

---

## 图片 (imagebox)
用于上传图片

**默认值支持：**
1. 数据联动（`linkInfo.linked`）

**校验支持：**
- 最少上传数（`verify.minValue`）
- 最多上传数（`verify.maxValue`）
- 限制文件大小（`verify.limitSize`）
- 限制文件类型（`verify.limitType`）
- 限制图片宽度（`verify.limitWidth`）
- 限制图片高度（`verify.limitHeight`）
- 图片裁切（`cropping`）

---

## 视频 (videobox)
用于上传视频

**默认值支持：**
1. 数据联动（`linkInfo.linked`）

**校验支持：**
- 最少上传数（`verify.minValue`）
- 最多上传数（`verify.maxValue`）
- 限制文件大小（`verify.limitSize`）
- 限制文件类型（`verify.limitType`）
- 限制视频宽度（`verify.limitWidth`）
- 限制视频高度（`verify.limitHeight`）
- 限制视频时长最小值（`verify.limitDurationMin`）
- 限制视频时长最大值（`verify.limitDurationMax`）
- 限制上传数量（`verify.limitCountVisible`）

---

## 联系人 (contact)
用于选择人员

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 数据联动（`linkInfo.linked`）
3. 上次填写内容（`latestValShow`）
4. 默认值为当前用户（`loginUserForValue`）
5. 关联字段获取默认值（`relationValueConfig`）：学号/手机号关联

**校验支持：**
- （无独立校验规则）

---

## 部门 (department)
用于选择部门

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 数据联动（`linkInfo.linked`）
3. 默认值为当前用户所在单位（`curUserOrg`）
4. 默认值为当前用户主管的部门（`curLeaderOrg`）

**校验支持：**
- （无独立校验规则）

---

## 所属人 (belonger)
用于选择所属人，默认当前用户

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 数据联动（`linkInfo.linked`）
3. 默认值为当前用户（`loginUserForValue`）
4. 关联字段获取默认值（`relationValueConfig`）：学号/手机号关联

**校验支持：**
- 必填（`verify.required`）

---

## 地址 (areamultiselect)
用于选择省市区地址

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 数据联动（`linkInfo.linked`）
3. 上次填写内容（`latestValShow`）

**校验支持：**
- 必须选至最后一级（`verify.requiredLastStep`）

---

## 定位 (location)
用于获取地理位置

**默认值支持：**
1. 自定义定位方式（`defaultValueConfig`）：0-获取当前位置 / 1-从地图中选择
2. 数据联动获取定位值（`locationValue`）
3. 默认值为当前位置（`currentLocation`）

**校验支持：**
- （无独立校验规则）

---

## 富文本 (richtext)
用于富文本编辑器，支持图文混排

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）
2. 数据联动（`linkInfo.linked`）

**校验支持：**
- 字符长度限制（`verify.charLimit`）：最大长度/最小长度

---

## 滑动条 (slider)
通过滑动选择数值

**默认值支持：**
（通过 `values` 默认值字段设置初始值）

**校验支持：**
- （无独立校验规则，通过 `sliderRange` 限定范围）

---

## 评分 (rate)
星级评分组件

**默认值支持：**
1. 自定义（`hasDefaultValue` + `defaultValueStr`）

**校验支持：**
- （无独立校验规则，通过 `rateOptions` 配置星星数量与分值）

---

## 计算公式 (computeinput)
自动根据公式计算数值，不可手动编辑

**默认值支持：**
（不适用，数值由公式计算得出）

**校验支持：**
- 中文大写显示（`verify.chinese`）
- 百分比显示（`verify.percentage`）

---

## 自动编号 (autonumber)
自动生成编号，不可手动编辑

**默认值支持：**
（不适用，编号由系统自动生成，通过 `formatConfig` 配置编号规则）

**校验支持：**
- （无独立校验规则）

---

## 说明文字 (captiontext)
纯展示文本，不可填写

**默认值支持：**
（不适用，展示类组件）

**校验支持：**
（不适用，展示类组件）

---

## 按钮 (button)
操作按钮，可配置打开URL

**默认值支持：**
（不适用）

**校验支持：**
（不适用）

---

## 子表单 (detailcombox)
支持添加多行子项的表单容器

**默认值支持：**
1. 子组件默认值（`defaultCompts` / `defaultComptsInfo`）：默认行数、每行子组件的默认值

**校验支持：**
- （校验依赖子表单内各子组件的独立校验规则）

---

## 选择数据 (relateddata)
从已有表单/审批数据中选择

**默认值支持：**
（不适用，数据来源于已关联的表单数据）

**校验支持：**
- （无独立校验规则）

---

## 关联审批 (relatedaprv)
关联已有的审批单

**默认值支持：**
（不适用，审批单由用户手动选择）

**校验支持：**
- （无独立校验规则）

---

## 直播 (livevideo)
直播入口

**默认值支持：**
（不适用）

**校验支持：**
- （无独立校验规则）

---

## 手写签名 (signature)
手写签名板

**默认值支持：**
（不适用）

**校验支持：**
- （无独立校验规则）

---

## 请假套件 (leavekit)
请假审批专用套件，包含请假类型、开始/结束时间、时长等字段

**默认值支持：**
（不适用，套件类型组件由系统默认逻辑控制）

**校验支持：**
- 必填（`verify.required`）
- 日期区间校验（`verify.dateRange`）：开始时间不能晚于结束时间

---

## 销假套件 (leavecancellationkit)
销假审批专用套件

**默认值支持：**
（不适用，套件类型组件由系统默认逻辑控制）

**校验支持：**
- 必填（`verify.required`）

---

## 外出套件 (gooutkit)
外出审批专用套件，包含开始时间、结束时间、时长

**默认值支持：**
（不适用，套件类型组件由系统默认逻辑控制）

**校验支持：**
- 必填（`verify.required`）
- 日期区间校验（`verify.dateRange`）：开始时间不能晚于结束时间

---

## 加班套件 (overtimekit)
加班审批专用套件，包含开始时间、结束时间、时长

**默认值支持：**
（不适用，套件类型组件由系统默认逻辑控制）

**校验支持：**
- 必填（`verify.required`）
- 日期区间校验（`verify.dateRange`）：开始时间不能晚于结束时间

---

## 补卡套件 (punchkit)
补卡审批专用套件，包含补卡时间、补卡类型

**默认值支持：**
（不适用，套件类型组件由系统默认逻辑控制）

**校验支持：**
- 必填（`verify.required`）
