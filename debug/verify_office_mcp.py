"""office-mcp 完整验证：连接 → 列出工具 → 按提示内容调用。

提示内容：fid=97253
  表单 id 3414870 / 3414871（type=0）
  审批 id 300327 / 300328（type=1）
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv(override=True)

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND)

from services.mcp_service import mcp_manager

FID = 97253
CASES = [
    # (说明, 工具名, 参数)
    ("echo 自检", "office-mcp.office_mcp_echo", {"message": "hello office-mcp"}),
    ("表单字段配置 3414870 (type=0)", "office-mcp.office_form_compts_info", {"formType": 0, "formId": 3414870, "fid": FID}),
    ("表单字段配置 3414871 (type=0)", "office-mcp.office_form_compts_info", {"formType": 0, "formId": 3414871, "fid": FID}),
    ("审批字段配置 300327 (type=1)", "office-mcp.office_form_compts_info", {"formType": 1, "formId": 300327, "fid": FID}),
    ("审批字段配置 300328 (type=1)", "office-mcp.office_form_compts_info", {"formType": 1, "formId": 300328, "fid": FID}),
    ("表单页面链接 3414870 (type=0)", "office-mcp.office_form_apply_page_url", {"formType": 0, "formId": 3414870, "fid": FID}),
]


async def main():
    await mcp_manager.start()
    if not mcp_manager.is_ready():
        print("FAIL: office-mcp 未就绪")
        await mcp_manager.close()
        return

    print("已连接，可用工具:", [t.name for t in mcp_manager.list_tools()], "\n")

    for label, tool, args in CASES:
        print(f"=== {label} ===")
        try:
            result = await mcp_manager.call_tool(tool, args)
            # 截断输出，避免过长
            if len(result) > 2000:
                result = result[:2000] + "…(已截断)"
            print("result:", result[:2000])
        except Exception as e:
            print("调用异常:", e)
        print()

    await mcp_manager.close()


asyncio.run(main())
