import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator, ValidationError, validate

class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "contracts" / "FULL_contract_with_data.json"
        cls.tool = json.loads(path.read_text(encoding="utf-8-sig"))["tools"][0]
    def test_schemas_and_samples(self):
        Draft202012Validator.check_schema(self.tool["inputSchema"])
        Draft202012Validator.check_schema(self.tool["outputSchema"])
        for item in self.tool["mockResponses"]: validate(item["result"], self.tool["outputSchema"])
    def test_blank_input_is_rejected(self):
        value = {"referenceName":"   ","thicknessMm":14,"material":"AH36","boundaries":{"top":None,"bottom":None,"left":None,"right":None}}
        with self.assertRaises(ValidationError): validate(value, self.tool["inputSchema"])
    def test_result_consistency_is_enforced(self):
        invalid = [{"success":True,"message":"ok","objectId":None,"errorCode":None},{"success":True,"message":"ok","objectId":"id","errorCode":"ERROR"},{"success":False,"message":"bad","objectId":"id","errorCode":"ERROR"},{"success":False,"message":"bad","objectId":None,"errorCode":None}]
        for value in invalid:
            with self.assertRaises(ValidationError): validate(value, self.tool["outputSchema"])
