import os
import unittest

from agent.graph import graph


RUN_LOCAL_E2E = os.getenv("RUN_LOCAL_E2E") == "1"


@unittest.skipUnless(
    RUN_LOCAL_E2E,
    "设置 RUN_LOCAL_E2E=1 后运行真实 Ollama 端到端测试",
)
class LocalOllamaEndToEndTests(unittest.TestCase):
    def test_create_panel_and_reject_non_creation_request(self) -> None:
        create_result = graph.invoke(
            {
                "user_input": (
                    "请在第100肋位创建一块厚度为14mm、"
                    "材料为AH36的板架，边界 >SL10"
                )
            }
        )

        self.assertIsNone(create_result.get("error"))
        self.assertTrue(create_result["cad_result"].success)
        self.assertEqual(
            create_result["panel_request"].reference_plane,
            "FR100",
        )

        unsupported_result = graph.invoke(
            {"user_input": "AH36是什么材料？"}
        )

        self.assertEqual(
            unsupported_result["action_plan"].action,
            "unsupported",
        )
        self.assertNotIn("cad_result", unsupported_result)


if __name__ == "__main__":
    unittest.main()
