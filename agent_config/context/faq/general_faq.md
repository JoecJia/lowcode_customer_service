# 常见问题 (FAQ)

### Q: 汇总数据（如数据工厂生成的）如何实现“点击查看”显示原始明细？
A: 有两种主要实现方式：
1. **数据工厂“多行合并”法**：在数据工厂的 [分组汇总](file:///d:/Joec's%20code/project-3%EF%BC%9Acustomer_service/agent_config/context/product_docs/data_factory_guide.md#L226) 节点中，将需要查看的明细字段汇总方式设为“多行合并”，作为数据流最后一个节点。同步到新表单后，明细将以“子表单”形式展示。
2. **管理页“打开关联表”法**：在新表单的 [管理页设计](file:///d:/Joec's%20code/project-3%EF%BC%9Acustomer_service/agent_config/context/product_docs/form_usage_guide.md#L7237) 中，新建一个功能为“打开关联表”的右侧按钮。通过维度字段（如班级、课程等）设置关联条件，即可实时跳转查阅原始表的明细数据。

### Q: 数据联动怎么配？
A: 表单和审批的数据联动在表单和审批的创建页，选中字段，并在右侧字段属性的默认值或者选项中配置，选项数据联动会在点击展开选项列表时触发，默认值数据联动会在联动条件中当前表的联动字段值改变时触发，如果未配置联动字段则在进入页面时触发

### Q: 数据同步
A: 表单/审批数据同步给其他系统的方式主要有三种： 1.表单推数据给对方，可以写接口配置到表单数据推送中，实时性较高，需要正确匹配数据结构（数据中台同步表单数据采用此模式）； 2.业务团队中间包装一层，先通过公司内部表单接口从表单中取到数据，匹配上对方系统的数据结构后，按照对方接口要要求的格式推送给对方系统（对接客户的第三方系统通常采用此模式）； 3.对方业务系统直接调用表单接口取到数据后，存入己方数据库，需要提供给对方第三方表单接口和表单的字段结构，字段结构包括字段标题，字段别名，字段类型。 接口说明： 公司内部使用的接口文档： 1.表单：https://cxapi.chaoxing.com/web/#/653656295 2.审批：https://cxapi.chaoxing.com/web/#/653656296 ▲注意：以上接口需要连接VPN才能打开，否则会403。 ▲sign和key申请方式：①在超星集团下 低代码产品接口授权 应用中申请；②点击链接申请：https://16q.cn/JvjCDP 第三方使用的接口： 1.表单第三方数据接口文档：https://document.chaoxing.com/web/#/71 ▲sign和key申请链接：http://16q.cn/Ld1oBI

**相似问法：** 表单数据同步给第三方、如何获取表单数据

### Q: 产品开通
A: 开通产品，请填写开通表：http://16q.cn/JoyAWm

**相似问法：** 开通、聚合表开通、数据工厂开通、报告开通、报表开通、文字识别开通、业务流开通

### Q: 拆分数组
A: 可以通过子表单整体数据联动和公式编辑将数组中的内容拆分至子表单中，具体操作方法参考视频 https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=-471600810&timestamp=1786424426781&showAppBar=true&puid=168034620&autoPreview=true&resid=1293921023780098048&objectId=&signature=7ebfa171e7c32552166dd7dedb4aba29

**相似问法：** 数组拆分

### Q: 公式编辑使用说明
A: 公式不会写，看着这篇就够了：https://vptbfpqk2e.feishu.cn/docx/YhwvdStn3oEbExxGDw6cMIH7nMe?from=from_copylink

**相似问法：** 公式编辑怎么用、公式应该怎么写

### Q: 表单更新日志
A: https://document.chaoxing.com/web/#/109/1248

**相似问法：** 表单近期更新的新功能、表单最近更新的功能、审批更新日志

### Q: 图表引擎使用说明
A: 请您查收！😃https://fe.chaoxing.com/front/subject/index.html#/details/D02A4A09-B45C-4331-9B08-B5517804D06E

**相似问法：** 图表引擎说明文档、图表如何使用

### Q: 座位预约使用说明
A: 请您查收！😆https://document.chaoxing.com/web/#/102/1221

**相似问法：** 座位预约说明文档

### Q: 数据工厂使用说明
A: 请您查收！🥰https://document.chaoxing.com/web/#/103/1237

**相似问法：** 数据工程说明文档

### Q: 审批使用说明
A: 请您查收！😊https://document.chaoxing.com/web/#/99

**相似问法：** 审批说明文档

### Q: 表单使用说明
A: 请您查收！😃https://document.chaoxing.com/web/#/120/1889

**相似问法：** 表单说明文档、表单操作手册

### Q: 万能打印使用说明
A: 万能打印使用说明：https://sharewh2.xuexi365.com/share/02ed1abd-3b89-4d52-92b5-a549bac5204e?t=3

### Q: 万能打印常见问题
A: 万能打印FAQ ：https://sharewh2.xuexi365.com/share/1fcb97a9-75aa-4463-8dc3-c0050271e4cc?t=3

**相似问法：** 打印常见问题、打印格式不对

### Q: 信息查询方案
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=1811470683&timestamp=1786423015398&showAppBar=true&puid=168034620&autoPreview=true&resid=1293914789954940928&objectId=&signature=45a20d25ef3eaa35b564b80c11a215a4

### Q: 表单方案
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=-1244873664&timestamp=1786423006649&showAppBar=true&puid=168034620&autoPreview=true&resid=1293914805356425216&objectId=&signature=48b0969a0513eb08503966227610def2

### Q: 审批方案
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=-22326319&timestamp=1786422997259&showAppBar=true&puid=168034620&autoPreview=true&resid=1293914812657602560&objectId=&signature=a6577c86676b613dd19cfb4cde5bec95

### Q: 考勤方案
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=1589239893&timestamp=1786423033022&showAppBar=true&puid=168034620&autoPreview=true&resid=1293914803821309952&objectId=&signature=bb7364d6ff2bf6b7b0cf13a317c203b9

### Q: 图表引擎方案
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=1303116857&timestamp=1786423024357&showAppBar=true&puid=168034620&autoPreview=true&resid=1293914809075666944&objectId=&signature=b3ff2f6101f30d1b981c5de735a42753

### Q: 座位预约系统方案
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=1303996530&timestamp=1786423040695&showAppBar=true&puid=168034620&autoPreview=true&resid=1293914801002737664&objectId=&signature=573e129d694fe0c66cb2fe5ff6d3cf4c

### Q: 预约引擎方案
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=868983986&timestamp=1786423053030&showAppBar=true&puid=168034620&autoPreview=true&resid=1293914806655553536&objectId=&signature=c1e8dee79f425a340b46f972c713565c

### Q: 蜂鸟办公系统参数
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=170403042&timestamp=1786421384912&showAppBar=true&puid=168034620&autoPreview=true&resid=1293908295921270784&objectId=&signature=cbb916b4f0aed64075dac1a6628d873d

### Q: 图表参数
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=-1769320182&timestamp=1786421305295&showAppBar=true&puid=168034620&autoPreview=true&resid=1293907103325999104&objectId=&signature=59bffcb62f48599cdf9af594f88ee11d

**相似问法：** 仪表盘参数

### Q: 空间预约参数
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=-986868769&timestamp=1786421297866&showAppBar=true&puid=168034620&autoPreview=true&resid=1293907107221069824&objectId=&signature=0a7dcb4824a964b7320506aad6c8c3fb

### Q: 信息查询参数
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=702766862&timestamp=1786421291539&showAppBar=true&puid=168034620&autoPreview=true&resid=1293907104148078592&objectId=&signature=95751ae0c4128c8b3415c3803e6fb39b

### Q: 座位预约参数
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=726041986&timestamp=1786421266929&showAppBar=true&puid=168034620&autoPreview=true&resid=1293907109395152896&objectId=&signature=b952f9ab5dd65743ecfc22025f3797c0

### Q: 审批参数
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=726041986&timestamp=1786421266929&showAppBar=true&puid=168034620&autoPreview=true&resid=1293907109395152896&objectId=&signature=b952f9ab5dd65743ecfc22025f3797c0

### Q: 表单引擎参数
A: https://pan-yz.cldisk.com/v2/external/resourceDetail.html?appid=1D734FA7-035A-4DEC-AA1C-DD63331D9267&nonce=27567498&timestamp=1786421256927&showAppBar=true&puid=168034620&autoPreview=true&resid=1293907103447625728&objectId=&signature=226fcb02aeff2a3f4b7bdd04c36cfd7a

**相似问法：** 表单参数

### Q: 附件上传的大小限制
A: 附件字段上传单个文件最多2G，PC端上传支持开通至15G

### Q: 数据工厂如何开通
A: http://16q.cn/JoyAWm 请填写产品开通审批表，表内有相应的产品说明文档，如有需要可进行查看。

**相似问法：** 聚合表如何开通

### Q: 负责人是谁？
A: 我猜您是想查询某个产品的负责人，您可以在学习通内将单位切换至超星集团，然后在超星集团的应用中找到「超星产品名录」，在这里或许就能搜到您想找的人啦！快去试试吧！

**相似问法：** 引擎的负责人是谁？、产品经理是谁、产品是谁

### Q: 表单数据计算中，请勿离开页面弹窗为什么会出现？
A: 出现该弹窗的原因可能是表单内存在的数据联动、公式编辑、计算公式等内容还未计算完成

**相似问法：** 弹窗提示表单数据计算中是什么原因？

### Q: 后台如何导出不脱敏的数据？
A: 需要在高级设置-权限设置-字段权限中，取消勾选小齿轮内的「数据脱敏显示」

**相似问法：** 后台如何导出明文的数据？、如何导出不加密的数据？、脱敏

### Q: 表单设置了免登录还是需要登录学习通账号
A: 若想要表单免登录，不仅需要在高级设置-前台应用设置-提交设置处勾选免登录，还需要在微服务应用管理-应用详情处勾选“不需要登录”选项。

**相似问法：** 为什么设置了免登录还是需要登录、表单设置了免登录，但是打开微信端的网址还是需要登录是什么原因呢

### Q: 表单批量导入时会校验配置的规则吗
A: 在导入按钮的配置中勾选需要校验项，导入的时候即可实现校验。

**相似问法：** 表单批量导入时怎么校验配置规则

### Q: 如何校验表单内多个字段组合值是否重复
A: 方法1：创建一个单行输入字段，通过公式编辑将多个字段合并到一起，再开启单行输入字段的不允许重复值配制，需要保证单行输入字段可见，不可见时，不会校验重复值 方法2：添加一个字段配置数据联动，将需要校验的字段作为数据联动条件，去联动另一张表中的任一必填字段，如果有联动结果，说明字段已存在，如没有联动结果，说明字段不存在，可配合提交校验实现重复校验，公式：if(isempty(重复值校验字段),true,false)。

**相似问法：** 多表校验字段是否存在、字段组合重复值校验
