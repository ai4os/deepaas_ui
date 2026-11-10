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

"""Parse the API specification of a DEEPaaS model.

DEEPaaS 2.x publishes a Swagger 2.0 specification, whereas DEEPaaS 3.x
publishes an OpenAPI 3 specification. This module converts both of them to the
format used by the UI, that follows the Swagger 2.0 one:

* inputs: list of parameters, with their ``name``, ``type``, ``description``,
  ``default``, ``enum``, ``minimum``, ``maximum`` and ``format`` keys. Files
  have ``file`` as type.
* mimes: list of media types that the predict endpoint can return.
* outputs: properties of the response schema of the model (with their
  ``type``, ``description`` and ``format`` keys), or ``None`` if the model does
  not define a response schema.
"""

# Name of the response schema of the models, in both DEEPaaS versions
RESPONSE_SCHEMA = "ModelPredictionResponse"


def find_predict_path(specs):
    """Return the path of the predict endpoint of the (first) model."""
    paths = [
        p for p in specs["paths"]
        if p.endswith("/predict/") or p.endswith("/predict")
    ]
    if not paths:
        raise Exception("No model could be found.")
    # Prefer the v2 paths, with a trailing slash
    paths.sort(key=lambda p: not p.endswith("/"))
    return paths[0]


def parse_spec(specs):
    """Parse the specification of a DEEPaaS API.

    :param specs: the specification, as returned by ``/swagger.json``.
    :returns: a dict with the ``path`` of the predict endpoint, and its
        ``inputs``, ``mimes`` and ``outputs`` (see the module documentation).
    """
    path = find_predict_path(specs)
    if "openapi" in specs:
        parsed = _parse_openapi(specs, path)
    else:
        parsed = _parse_swagger(specs, path)
    parsed["path"] = path
    return parsed


def _parse_swagger(specs, path):
    """Parse a Swagger 2.0 specification (DEEPaaS 2.x)."""
    operation = specs["paths"][path]["post"]

    inputs = []
    for param in operation["parameters"]:
        param = dict(param)
        # We default type to string because sometimes modules are not using
        # inputs correctly (eg. YOLOV8: "classes" param)
        param["type"] = param.get("type", "string")
        inputs.append(param)

    mimes = [m for m in operation.get("produces", []) if m != "*/*"]

    outputs = None
    definition = specs.get("definitions", {}).get(RESPONSE_SCHEMA)
    if definition is not None:
        outputs = definition.get("properties", {})

    return {"inputs": inputs, "mimes": mimes, "outputs": outputs}


def _resolve(specs, schema):
    """Resolve a "$ref" to a schema of the specification."""
    ref = schema.get("$ref")
    if ref is None:
        return schema
    # e.g. "#/components/schemas/ModelPredictionResponse"
    node = specs
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def _flatten(specs, schema):
    """Flatten an OpenAPI 3 schema to the Swagger 2.0 style used by the UI.

    Optional values are documented as ``anyOf: [<type>, null]``, so we take
    the first type that is not null, keeping the description, default, etc.
    """
    schema = dict(_resolve(specs, schema))
    any_of = schema.pop("anyOf", None)
    if any_of:
        types = [s for s in any_of if s.get("type") != "null"]
        if types:
            base = dict(_resolve(specs, types[0]))
            base.update(schema)
            schema = base
    return schema


def _is_binary(schema):
    # Files are documented with the "binary" format, or (in recent FastAPI
    # versions, following OpenAPI 3.1) with a "contentMediaType"
    return schema.get("format") == "binary" or "contentMediaType" in schema


def _is_file(schema):
    if _is_binary(schema):
        return True
    return any(_is_binary(s) for s in schema.get("anyOf", []))


def _parse_openapi(specs, path):
    """Parse an OpenAPI 3 specification (DEEPaaS 3.x)."""
    operation = specs["paths"][path]["post"]

    inputs = []
    for param in operation.get("parameters", []):
        if param.get("in") != "query":
            continue
        item = _flatten(specs, param.get("schema", {}))
        item["name"] = param["name"]
        item["in"] = "query"
        item["required"] = param.get("required", False)
        if param.get("description"):
            item["description"] = param["description"]
        # We default type to string because sometimes modules are not using
        # inputs correctly
        item["type"] = item.get("type", "string")
        inputs.append(item)

    # Files are sent in the multipart body of the request
    body = operation.get("requestBody", {}).get("content", {})
    form = body.get("multipart/form-data")
    if form is not None:
        schema = _resolve(specs, form["schema"])
        required = set(schema.get("required", []))
        for name, prop in schema.get("properties", {}).items():
            if not _is_file(prop):
                continue
            item = {
                "name": name,
                "in": "formData",
                "type": "file",
                "required": name in required,
            }
            if prop.get("description"):
                item["description"] = prop["description"]
            inputs.append(item)

    content = operation.get("responses", {}).get("200", {}).get("content", {})
    mimes = [m for m in content if m != "*/*"]

    outputs = None
    json_schema = content.get("application/json", {}).get("schema", {})
    if json_schema.get("$ref", "").endswith("/" + RESPONSE_SCHEMA):
        schema = _resolve(specs, json_schema)
        outputs = {
            name: _flatten(specs, prop)
            for name, prop in schema.get("properties", {}).items()
        }

    return {"inputs": inputs, "mimes": mimes, "outputs": outputs}
