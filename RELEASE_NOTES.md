## 测试用例步骤聚类分析工具

### Windows 免安装版

**下载 `testcase_cluster_tool_windows.zip` 后解压即可使用，无需安装 Python。**

#### 使用方法
1. 解压 zip 文件
2. 双击 `testcase_cluster_tool.exe`
3. 浏览器自动打开 http://127.0.0.1:5000

#### 包含内容
- `testcase_cluster_tool.exe` - 主程序
- `models/bge-large-zh-v1.5/` - 内置离线语义模型 (BAAI/bge-large-zh-v1.5, ~1.3GB)
- `sample_testcases.xlsx` - 示例测试用例文件
- `data/` - 数据库目录（运行时自动创建 testcase.db）
- `log/` - 日志目录（运行时自动生成按天滚动的日志文件）

#### 功能
- xlsx 文件导入（自动识别列映射，支持合并单元格，增量导入覆盖）
- 基于 DBSCAN 的语义聚类（相似度阈值 0.50~0.95 可调）
- 多模型支持：内置 bge-large-zh-v1.5 / 自定义本地模型 / 在线 API (OpenAI 兼容) / TF-IDF 轻量模式
- 按编号精确查询或按标题模糊查询用例
- 聚类重组视图：每条步骤标注所属簇及同簇的其他步骤
- 聚类结果总览与簇详情浏览
- 导出聚类结果为 xlsx（聚类总览 + 簇详情 + 用例聚类视图）
- 数据管理：单条/批量/按来源文件删除用例，清空全部数据
- 数据浏览：分页表格、排序、筛选、步骤预览、统计栏
- 聚类进度条：5 阶段百分比进度、批次进度、已用时间显示
- 聚类历史记录：保存/查看/对比/激活历史聚类结果
- 全界面中文化
- 维测日志记录（DEBUG/INFO/WARNING/ERROR，按天滚动）
