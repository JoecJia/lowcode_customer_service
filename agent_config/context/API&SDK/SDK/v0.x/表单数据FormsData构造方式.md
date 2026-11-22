
[TOC]

# 各字段举例
- **不支持的字段**：直播、计算公式、选择数据、说明文字、自动编号
- 注：创建字段对象时均可用 “字段id” 或 “字段别名” 来构造，如下例中的单行输入和多行输入

```java
FormsData formsData = new FormsData();
// 单行输入
formsData.addField(new EditinputField("uname", "张三"));
// 多行输入
formsData.addField(new EdittextareaField(2, "test"));
// 数字输入
formsData.addField(new NumberinputField(3, 888d));
// 滑动条
formsData.addField(new SliderField(4, 88));
// 单选
formsData.addField(new RadiobuttonField(5, "选项1"));
// 多选
formsData.addField(new ChecklistField(6, "选项1", "选项3"));
// 下拉框
formsData.addField(new SelectBoxField(7, "选项1"));
// 下拉复选
formsData.addField(new SelectMultiBoxField(8, "选项1", "选项2", "选项3"));
// 多级下拉
formsData.addField(new MultipleselectField(9, "选项1", "选项1"));
// 日期
formsData.addField(new DateinputField(11, date.getTime()));
// 日期区间
formsData.addField(new DatetimerangeField(12, date.getTime(), date.getTime()));
// 图片
ImageboxField imageboxField = new ImageboxField(13);
imageboxField.addValue("图片.jpg", "http://pan-yz.chaoxing.com/thumbnail/origin/8496cf4c214ea5d7e6ddbf0030bcc6e1", "8496cf4c214ea5d7e6ddbf0030bcc6e1", "3015", "jpg", 1670238673305L, "806602715512950800");
formsData.addField(imageboxField);
// 视频
VideoboxField videoboxField = new VideoboxField(14);
videoboxField.addValue("视频.mp4", "http://pan-yz.chaoxing.com/thumbnail/origin/a7a017c8e931ddfa2863b08f126991e0", "a7a017c8e931ddfa2863b08f126991e0", "4041543", "mp4", 1670238678078L, "27", "1920", "1080", "806602735544946700");
formsData.addField(videoboxField);
// 附件
FileuploadField fileuploadField = new FileuploadField(15);
fileuploadField.addValue("图片.jpg", "http://pan-yz.chaoxing.com/thumbnail/origin/8496cf4c214ea5d7e6ddbf0030bcc6e1", "8496cf4c214ea5d7e6ddbf0030bcc6e1", "3015", "jpg", 1670238673305L, "806602715512950800");
fileuploadField.addValue("视频.mp4", "http://pan-yz.chaoxing.com/thumbnail/origin/a7a017c8e931ddfa2863b08f126991e0", "a7a017c8e931ddfa2863b08f126991e0", "4041543", "mp4", 1670238678078L, "27", "1920", "1080", "806602735544946700");
fileuploadField.addValue("word.docx", "", "3acad9e3f18cf128e89af9d1644e824d", "12115", "docx", 1670238689336L, "806602782701506560");
formsData.addField(fileuploadField);
// 联系人多选
ContactField contactField = new ContactField(16, 143073485, "测试1");
contactField.addValue(143073510, "测试2");
formsData.addField(contactField);
// 部门多选
DepartmentField departmentField = new DepartmentField("17");
departmentField.addValue(716802, "部门A", -1L);
departmentField.addValue(744938, "部门B");
formsData.addField(departmentField);
// 子表单字段
DetailField detailField = new DetailField(18);
// 构造子表单内第一行
FormsData subFormsData1 = new FormsData();
subFormsData1.addField(new EditinputField(19, "子表单内单行输入"));
subFormsData1.addField(new EdittextareaField(20, "子表单内多行输入"));
subFormsData1.addField(new NumberinputField(21, 70d));
// 放入子表单
detailField.addSubField(subFormsData1);
// 构造子表单内第二行
FormsData subFormsData2 = new FormsData();
subFormsData1.addField(new EditinputField(19, "子单第二行"));
subFormsData1.addField(new EdittextareaField(20, "子多第二行"));
subFormsData1.addField(new NumberinputField(21, 70d));
// 放入子表单
detailField.addSubField(subFormsData2);
formsData.addField(detailField);
// 富文本
formsData.addField(new RichtextField(22, "<p element-id=\\\"init\\\">富文本字段666</p>"));
// 矩阵单选
MatrixradioField matrixradioField = new MatrixradioField(25);
// 第一行
matrixradioField.addSubField(26, "选项3");
matrixradioField.addSubField(27, "选项1");
// 第二行
matrixradioField.addSubField(26, "选项2");
formsData.addField(matrixradioField);
// 矩阵多选
MatrixcheckboxField matrixcheckboxField = new MatrixcheckboxField(28);
// 第一行
matrixcheckboxField.addSubField(29, "选项1", "选项2");
matrixcheckboxField.addSubField(30, "选项3");
// 第二行
matrixcheckboxField.addSubField(29, "选项1", "选项2", "选项3");
matrixcheckboxField.addSubField(30, "选项3");
formsData.addField(matrixcheckboxField);
// 按钮
formsData.addField(new ButtonField(31, "https://p.ananas.chaoxing.com/star3/origin/669ca80d6a0c5f74835bb936a41aabca.jpg", "https://mooc1.chaoxing.com/course-ans/course/coursepreviewmiddle?courseId=231019802&enc=41382db09a8777b7966fab02c0c92be1", "任鑫意", "测试"));
// 定位
formsData.addField(new LocationField(33, "河北省廊坊市三河市高楼镇留山大街2号三河市燕德宝汽车销售服务有限公司", "40.009032", "116.810968"));
// 地址
formsData.addField(new AreamultiselectField(34, "北京市", "北京市", "朝阳区"));
//手写签名
formsData.addField(new SignatureField(35, "https://pan-yz.chaoxing.com/thumbnail/origin/3bfed76d4a74a919482b30d42aad6d5c"));
//所属人
formsData.addField(new BelongerField(36, 143073485, "测试1"));
//调sdk接口
ApiModifyResponse saveByFormId = OfficeApiInvokeService.saveCustomFormsDataByFormId(170507,
																				    181635,
																				    58178393,
																				    null,
																				    false,
																				    1,
																				    formsData);
```

# 特殊字段说明
- 部门（serviceId不传默认为-1）
- 日期类型传时间戳
- 富文本字段必须是富文本数据，需要有html等标签，比如p标签
- 图片、视频、附件  方法参数说明如下：

|参数名   |含义   |
| ------------ | ------------ |
|name   |文件名   |
|fileUrl   |文件地址   |
|objectId   |文件对象   |
|byteSize   |文件原始字节数   |
|suffix   |文件后缀   |
|modifyDate   |更新时间（不传默认为当前时间戳）   |
|duration   |文件为视频时的时长（视频字段才有此参数）   |
|videoWidth   |文件为视频时的宽（视频字段才有此参数）   |
|videoHeight   |文件为视频时的高（视频字段才有此参数）   |
|resid   |附件文件resid   |


