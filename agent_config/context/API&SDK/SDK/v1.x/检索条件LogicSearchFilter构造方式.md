[TOC]

# 各字段举例
- **不支持的字段**：直播、手写签名、按钮、附件、图片、矩阵单选、矩阵多选、视频、选择数据、说明文字、关联审批、审批套件
- 支持且/或混合结构
![且/或混合结构](http://cxapi.chaoxing.com/server/index.php?s=/api/attachment/visitFile&sign=f65a777e8bc7547d5b331d131ebd3f4c)

- 注：创建字段对象时均可用 “字段id” 或 “字段别名” 来构造，如下例中的单行输入和多行输入
```java
// 高级检索
LogicSearchFilter logicSearchFilter = new LogicSearchFilter(SearchModelTypeEnum.OR);
// 单行输入（等于）
logicSearchFilter.addFilter(new EditinputSearchFilter("uname", SearchExpressTypeEnum.EQUALS, "张三"));
// 多行输入（不等于）
logicSearchFilter.addFilter(new EdittextareaSearchFilter(2, SearchExpressTypeEnum.NOT_EQUALS, "李四"));
// 数字输入（范围）
NumberinputSearchFilter numberinputSearchFilter = new NumberinputSearchFilter("3",
															 				   SearchExpressTypeEnum.GREATER_THEN_EQUALS,
																			    1.5,
																			    SearchExpressTypeEnum.LESS_THAN_EQUALS,
																				95.5);
logicSearchFilter.addFilter(numberinputSearchFilter);
// 滑动条（等于）
logicSearchFilter.addFilter(new SliderSearchFilter(4, SearchExpressTypeEnum.EQUALS, 66));
// 单选（等于任意一个）
logicSearchFilter.addFilter(new RadiobuttonSearchFilter(5, SearchExpressTypeEnum.CONTAINS_ANY, "选项1", "选项2", "选项3"));
// 多选（不等于任意一个）
logicSearchFilter.addFilter(new ChecklistSearchFilter(6, SearchExpressTypeEnum.CONTAINS_NO, "选项1", "选项2", "选项3"));
// 下拉（为空）
logicSearchFilter.addFilter(new SelectBoxSearchFilter(7, SearchExpressTypeEnum.IS_NULL));
// 下拉复选（不为空）
logicSearchFilter.addFilter(new SelectMultiBoxSearchFilter(8, SearchExpressTypeEnum.IS_NOT_NULL));
// 多级下拉（等于）
logicSearchFilter.addFilter(new MultipleselectSearchFilter(9, SearchExpressTypeEnum.LIKE, "选项1", "选项1"));
// 日期（范围）
DateinputSearchFilter dateinputSearchFilter = new DateinputSearchFilter(11,
																		  SearchExpressTypeEnum.GREATER_THEN_EQUALS,
																		  1670208240858L,
																		  SearchExpressTypeEnum.LESS_THAN_EQUALS,
																		  1670238349660L);
logicSearchFilter.addFilter(dateinputSearchFilter);
// 日期区间（结束时间等于）
logicSearchFilter.addFilter(new DatetimerangeSearchFilter(12, SearchExpressTypeEnum.EQUALS, 1670208240858L, DateTimeRangeSubIndexEnum.END_TIME));
// 联系人（等于任意一个）
logicSearchFilter.addFilter(new ContactSearchFilter(16, SearchExpressTypeEnum.CONTAINS_ANY, 143073510, 143073485));
// 部门（等于）
logicSearchFilter.addFilter(new DepartmentSearchFilter(17, SearchExpressTypeEnum.EQUALS, 716802));
// 富文本
logicSearchFilter.addFilter(new RichtextSearchFilter(22, SearchExpressTypeEnum.LIKE, "富文本666"));
// 计算公式（大于）
logicSearchFilter.addFilter(new ComputeinputSearchFilter(23, SearchExpressTypeEnum.GREATER_THAN, 22d));
// 自动编号（等于）
logicSearchFilter.addFilter(new AutonumberSearchFilter("24", SearchExpressTypeEnum.EQUALS, "000001"));
// 定位（等于）
logicSearchFilter.addFilter(new LocationSearchFilter(33, SearchExpressTypeEnum.LIKE, "河北省廊坊市三河市"));
// 地址（等于）
logicSearchFilter.addFilter(new AreamultiselectSearchFilter(34, SearchExpressTypeEnum.EQUALS, "北京市/北京市/朝阳区"));
// 所属人（等于）
logicSearchFilter.addFilter(new BelongerSearchFilter(36, SearchExpressTypeEnum.EQUALS, 143073510));
// 子条件1（且）
LogicSearchFilter subLogicSearchFilter = new LogicSearchFilter(SearchModelTypeEnum.AND);
subLogicSearchFilter.addFilter(new EditinputSearchFilter("1", SearchExpressTypeEnum.EQUALS, "张三"));
subLogicSearchFilter.addFilter(new ContactSearchFilter("16", SearchExpressTypeEnum.CONTAINS_ALL, 143073510, 143073485));
// 子条件1 的 子条件2（或）
LogicSearchFilter subLogicSearchFilter2 = new LogicSearchFilter(SearchModelTypeEnum.OR);
subLogicSearchFilter2.addFilter(new DateinputSearchFilter(11, SearchExpressTypeEnum.EQUALS, 1670208240858L));
subLogicSearchFilter2.addFilter(new NumberinputSearchFilter("3", SearchExpressTypeEnum.GREATER_THEN_EQUALS, 1.5));
subLogicSearchFilter2.addFilter(new SelectMultiBoxSearchFilter(9, SearchExpressTypeEnum.CONTAINS_ANY, "选项1", "选项2", "选项3"));
subLogicSearchFilter2.addFilter(new EditinputSearchFilter(1, SearchExpressTypeEnum.LIKE, "白"));
subLogicSearchFilter.addFilter(subLogicSearchFilter2);
logicSearchFilter.addFilter(subLogicSearchFilter);
// 请假套件--请假类型
logicSearchFilter.addFilter(new LeaveKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, Lists.newArrayList("事假"), LeaveKitSubIndexEnum.LEAVE_TYPE));
// 请假套件--开始时间
logicSearchFilter.addFilter(new LeaveKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, "2024-12-18 00:00", LeaveKitSubIndexEnum.START_TIME));
// 请假套件--结束时间
logicSearchFilter.addFilter(new LeaveKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, "2024-12-18 00:00", LeaveKitSubIndexEnum.END_TIME));
// 请假套件--销假状态（0：无需销假  1：到期未销假  2：销假中  3：已销假  4：未到请假时间  5：请假中）
logicSearchFilter.addFilter(new LeaveKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, Lists.newArrayList("3"), LeaveKitSubIndexEnum.LEAVE_CANCELLATION_STATUS));
// 请假套件--销假开始时间
logicSearchFilter.addFilter(new LeaveKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, "2024-12-18 00:00", LeaveKitSubIndexEnum.LEAVE_CANCELLATION_START_TIME));
// 请假套件--销假结束时间
logicSearchFilter.addFilter(new LeaveKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, "2024-12-18 00:00", LeaveKitSubIndexEnum.LEAVE_CANCELLATION_END_TIME));
// 外出套件--开始时间
logicSearchFilter.addFilter(new GoOutKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, "2024-12-18 00:00", GoOutKitSubIndexEnum.START_TIME));
// 外出套件--结束时间
logicSearchFilter.addFilter(new GoOutKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, "2024-12-18 00:00", GoOutKitSubIndexEnum.END_TIME));
// 加班套件--开始时间
logicSearchFilter.addFilter(new OvertimeKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, "2024-12-18 00:00", OvertimeKitSubIndexEnum.START_TIME));
// 加班套件--结束时间
logicSearchFilter.addFilter(new OvertimeKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, "2024-12-18 00:00", OvertimeKitSubIndexEnum.END_TIME));
// 补卡套件--补卡时间
logicSearchFilter.addFilter(new PunchKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, "2024-12-18 00:00"));
// 销假套件--请假类型
logicSearchFilter.addFilter(new LeaveCancellationKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, Lists.newArrayList("事假"), LeaveCancellationKitSubIndexEnum.LEAVE_TYPE));
// 销假套件--开始时间
logicSearchFilter.addFilter(new LeaveCancellationKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, "2024-12-18 00:00", LeaveCancellationKitSubIndexEnum.START_TIME));
// 销假套件--结束时间
logicSearchFilter.addFilter(new LeaveCancellationKitSearchFilter(1, SearchExpressTypeEnum.EQUALS, "2024-12-18 00:00", LeaveCancellationKitSubIndexEnum.END_TIME));
// 系统字段--提交人/发起人
logicSearchFilter.addFilter(new SubmitUserFilter(SearchExpressTypeEnum.EQUALS, Lists.newArrayList(58178393L)));
// 系统字段--审批人列表
logicSearchFilter.addFilter(new ApproveUserListFilter(SearchExpressTypeEnum.EQUALS, Lists.newArrayList(58178393L)));
// 系统字段--当前审批人
logicSearchFilter.addFilter(new CurrentApproveUserFilter(SearchExpressTypeEnum.EQUALS, Lists.newArrayList(58178393L)));
// 系统字段--抄送人列表
logicSearchFilter.addFilter(new CCUserListFilter(SearchExpressTypeEnum.EQUALS, Lists.newArrayList(58178393L)));
// 系统字段--审批状态
logicSearchFilter.addFilter(new ApproveStatusFilter(SearchExpressTypeEnum.EQUALS, Lists.newArrayList(ApproveStatusFilterEnum.DAI_SHEN_PI)));
// 系统字段--提交时间/发起时间
logicSearchFilter.addFilter(new InsertTimeFilter(SearchExpressTypeEnum.EQUALS, "2025-01-01 00:00"));
// 系统字段--更新时间
logicSearchFilter.addFilter(new UpdateTimeFilter(SearchExpressTypeEnum.EQUALS, "2025-01-01 00:00"));
// 系统字段--审批完成时间
logicSearchFilter.addFilter(new CompleteTimeFilter(SearchExpressTypeEnum.EQUALS, "2025-01-01 00:00"));
//调sdk接口
ApiSearchResponse formIdSearch = OfficeFormsApiInvokeService.formUserAdvanceSearchListByFormId(170507,
																								 181635,
																								 0,
																								 "143073510,143073485",
																								 0,
																								 null,
																								 logicSearchFilter,
																								 "inserttime",
																								 "asc",
																								 "2022-12-01 10:12:59",
																								 "2022-12-03 10:12:59",
																								 "2022-12-07 10:12:59",
																								 "2022-12-08 10:12:59",
																								 1,
																								 100);
```

# SearchModelTypeEnum类型说明
|枚举值   |含义   |
| ------------ | ------------ |
|OR   |或   |
|AND   |且   |

# SearchExpressTypeEnum类型说明
|枚举值   |含义   |
| ------------ | ------------ |
|EQUALS   |等于   |
|NOT_EQUALS   |不等于   |
|LIKE   |包含   |
|NOT_LIKE   |不包含   |
|CONTAINS_ANY   |等于(包含)任意一个   |
|CONTAINS_NO   |不等于(不包含)任意一个   |
|CONTAINS_ALL   |同时包含   |
|IS_NULL   |为空   |
|IS_NOT_NULL   |不为空   |
|GREATER_THAN   |大于   |
|GREATER_THEN_EQUALS   |大于等于   |
|LESS_THAN   |小于   |
|LESS_THAN_EQUALS   |小于等于   |
|RANGE   |选择范围   |

# 日期区间DateTimeRangeSubIndexEnum类型说明
|枚举值   |含义   |
| ------------ | ------------ |
|START_TIME   |开始时间   |
|END_TIME   |结束时间   |
|LENGTH   |时长   |

# 各字段可选SearchExpressTypeEnum类型
|字段   |可选类型   |
| ------------ | ------------ |
|联系人、部门、所属人<br>系统字段：审批人列表、当前审批人、抄送人列表   |EQUALS（等于）<br>NOT_EQUALS（不等于）<br>CONTAINS_ANY（等于任意一个）<br>CONTAINS_NO（不等于任意一个）<br>CONTAINS_ALL（同时包含）<br>IS_NULL（为空）<br>IS_NOT_NULL（不为空）   |
|单选、多选、下拉框、下拉复选、多级下拉   |EQUALS（等于）<br>NOT_EQUALS（不等于）<br>LIKE（包含）<br>NOT_LIKE（不包含）<br>CONTAINS_ANY（等于任意一个）<br>CONTAINS_NO（不等于任意一个）<br>CONTAINS_ALL（同时包含）<br>IS_NULL（为空）<br>IS_NOT_NULL（不为空）   |
|单行输入、多行输入、富文本、自动编号、定位、地址   |EQUALS（等于）<br>NOT_EQUALS（不等于）<br>LIKE（包含）<br>NOT_LIKE（不包含）<br>IS_NULL（为空）<br>IS_NOT_NULL（不为空）   |
|数字输入、滑动条、计算公式、日期、日期区间<br>审批套件（开始时间、结束时间、补卡时间）<br>系统字段（提交时间/发起时间、更新时间、审批完成时间）   |EQUALS（等于）<br>NOT_EQUALS（不等于）<br>IS_NULL（为空）<br>IS_NOT_NULL（不为空）<br>GREATER_THAN（大于）<br>GREATER_THEN_EQUALS（大于等于）<br>LESS_THAN（小于）<br>LESS_THAN_EQUALS（小于等于）   |
|请假套件--请假类型、销假套件--请假类型<br>系统字段（提交人/发起人、审批状态） | EQUALS（等于）<br>NOT_EQUALS（不等于）<br>CONTAINS_ANY（等于任意一个）<br>CONTAINS_NO（不等于任意一个）|

