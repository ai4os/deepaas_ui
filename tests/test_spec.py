# -*- coding: utf-8 -*-

# Copyright 2025 Spanish National Research Council (CSIC)
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Tests for the parsing of the DEEPaaS API specifications.

The specifications in tests/data were obtained from DEEPaaS 2.6.0 (Swagger
2.0) and DEEPaaS 3.0.0 (OpenAPI 3.1, with FastAPI 0.111 and with a recent
version), serving the ai4os-demo-app model.
"""

import json
from pathlib import Path

import pytest

import spec

DATA = Path(__file__).parent / "data"
PATH = "/v2/models/ai4os_demo_app/predict/"


def _load(name):
    with open(DATA / name) as f:
        return spec.parse_spec(json.load(f))


@pytest.fixture(
    scope="module",
    params=[
        "deepaas-v2-demo.json",
        "deepaas-v3-demo.json",
        # Recent FastAPI versions document files with "contentMediaType"
        "deepaas-v3-demo-fastapi-latest.json",
    ],
)
def parsed(request):
    return _load(request.param)


def _inputs(parsed):
    # DEEPaaS 2.x also documents the "accept" parameter, that the UI ignores
    return {i["name"]: i for i in parsed["inputs"] if i["name"] != "accept"}


def test_path(parsed):
    assert parsed["path"] == PATH


def test_inputs(parsed):
    inputs = _inputs(parsed)
    assert list(inputs) == [
        "demo_str",
        "demo_str_choice",
        "demo_password",
        "demo_int",
        "demo_int_range",
        "demo_float",
        "demo_bool",
        "demo_dict",
        "demo_list_of_floats",
        "demo_image",
        "demo_audio",
        "demo_video",
    ]
    types = {name: i["type"] for name, i in inputs.items()}
    assert types == {
        "demo_str": "string",
        "demo_str_choice": "string",
        "demo_password": "string",
        "demo_int": "integer",
        "demo_int_range": "integer",
        "demo_float": "number",
        "demo_bool": "boolean",
        "demo_dict": "string",
        "demo_list_of_floats": "array",
        "demo_image": "file",
        "demo_audio": "file",
        "demo_video": "file",
    }


def test_input_details(parsed):
    inputs = _inputs(parsed)
    assert inputs["demo_str"]["default"] == "some-string"
    assert inputs["demo_str_choice"]["enum"] == ["choice1", "choice2"]
    assert inputs["demo_password"]["format"] == "password"
    assert inputs["demo_int_range"]["minimum"] == 1
    assert inputs["demo_int_range"]["maximum"] == 100
    assert inputs["demo_bool"]["default"] is True
    assert inputs["demo_list_of_floats"]["default"] == [0.1, 0.2, 0.3]
    assert "image" in inputs["demo_image"]["description"]
    assert "audio" in inputs["demo_audio"]["description"]
    assert inputs["demo_image"]["required"] is True


def test_mimes(parsed):
    assert parsed["mimes"] == ["application/json", "application/zip", "image/*"]


def test_outputs(parsed):
    outputs = parsed["outputs"]
    assert outputs is not None
    assert outputs["demo_int"]["type"] == "integer"
    assert outputs["demo_dict"]["type"] == "object"
    assert outputs["labels"]["type"] == "array"
    assert outputs["demo_image"]["type"] == "string"
    assert outputs["demo_image"]["description"] == "image"
    assert outputs["demo_password"]["format"] == "password"


def test_same_result_for_both_versions():
    v2, v3 = _load("deepaas-v2-demo.json"), _load("deepaas-v3-demo.json")
    keys = ("name", "type", "enum", "default", "minimum", "maximum")

    def summary(parsed):
        # NOTE: only the "password" format is used by the UI (DEEPaaS 2.x also
        # documents formats such as "int32")
        return [
            dict(
                {k: i.get(k) for k in keys},
                password=i.get("format") == "password",
            )
            for i in parsed["inputs"]
            if i["name"] != "accept"
        ]

    assert summary(v2) == summary(v3)
    assert v2["mimes"] == v3["mimes"]
    assert set(v2["outputs"]) == set(v3["outputs"])
    for name in v2["outputs"]:
        assert v2["outputs"][name].get("type") == v3["outputs"][name].get("type")


def test_no_response_schema():
    with open(DATA / "deepaas-v3-demo.json") as f:
        specs = json.load(f)
    content = specs["paths"][PATH]["post"]["responses"]["200"]["content"]
    content["application/json"]["schema"] = {"$ref": "#/components/schemas/Prediction"}
    assert spec.parse_spec(specs)["outputs"] is None


def test_no_model():
    with pytest.raises(Exception, match="No model"):
        spec.parse_spec({"paths": {"/v2/": {}}})
