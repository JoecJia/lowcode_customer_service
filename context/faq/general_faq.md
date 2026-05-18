# 常见问题 (FAQ)

### Q: 汇总数据（如数据工厂生成的）如何实现“点击查看”显示原始明细？
A: 有两种主要实现方式：
1. **数据工厂“多行合并”法**：在数据工厂的 [分组汇总](file:///d:/Joec's%20code/project-3%EF%BC%9Acustomer_service/context/product_docs/data_factory_guide.md#L226) 节点中，将需要查看的明细字段汇总方式设为“多行合并”，作为数据流最后一个节点。同步到新表单后，明细将以“子表单”形式展示。
2. **管理页“打开关联表”法**：在新表单的 [管理页设计](file:///d:/Joec's%20code/project-3%EF%BC%9Acustomer_service/context/product_docs/form_usage_guide.md#L7237) 中，新建一个功能为“打开关联表”的右侧按钮。通过维度字段（如班级、课程等）设置关联条件，即可实时跳转查阅原始表的明细数据。
