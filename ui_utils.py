# -*- coding: utf-8 -*-

# Copyright 2021 Spanish National Research Council (CSIC)
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

import base64
import inspect
import json
import mimetypes
from pathlib import Path
import re
import requests
import tempfile
import warnings

import gradio as gr


session = requests.Session()


def api2gr_inputs(api_inp):
    """
    Transform DEEPaaS webargs to Gradio inputs.
    """
    gr_inp = []
    for i in api_inp:

        if i['name'] == 'accept':
            # do not show the "accept" MIME param in the Gradio interface
            continue

        info = i.get('description', '').split('\n\n')[0]  # the split('\n\n') is used to remove the HTML code that Swagger adds automatically

        if 'enum' in i.keys():  # could also be gr.Radio()
            tmp = gr.Dropdown(
                choices=i['enum'],
                value=i.get('default', None),
                label=i['name'],
                info=info,
                )
        elif i['type'] in ['integer', 'number']:
            if (i['type'] == 'integer') and {'minimum', 'maximum'}.issubset(i.keys()):
                tmp = gr.Slider(
                    value=i.get('default', None),
                    minimum=i.get('minimum', None),
                    maximum=i.get('maximum', None),
                    step=1,
                    label=i['name'],
                    info=info,
                    )
            else:
                tmp = gr.Number(
                    value=i.get('default', None),
                    label=i['name'],
                    info=info,
                    )
        elif i['type'] in ['boolean']:
            tmp = gr.Checkbox(
                value=i.get('default', None),
                label=i['name'],
                info=info,
                )
        elif i['type'] in ['string']:
            tmp = gr.Textbox(
                value=i.get('default', None),
                label=i['name'],
                info=info,
                )
        elif i['type'] in ['array']:
            tmp = gr.Textbox(
                value=i.get('default', None),
                label=i['name'],
                info=info,
                )
        elif i['type'] == 'file':
            desc = i.get('description', '').lower()

            # If more than one file-type is in description (eg. happens in YOLO),
            # then use a generic file component
            filetypes = ['image', 'audio', 'video']
            if sum([ftype in desc for ftype in filetypes]) >= 2:
                tmp = gr.File(
                    label=i['name'],
                    )

            elif 'image' in desc:
                tmp = gr.Image(
                    type='filepath',
                    label=i['name'],
                    )
            elif 'audio' in desc:
                tmp = gr.Audio(
                    type='filepath',
                    label=i['name'],
                    )
            elif 'video' in desc:
                tmp = gr.Video(
                    label=i['name'],
                    )
            else:
                # If media type not found, allow uploading as a generic file
                warnings.warn(
                    f"""
                    You should include the media type in the `{i['name']}` arg description for nice Gradio rendering.
                    Supported media types: image, video, audio.
                    """)
                tmp = gr.File(
                    label=i['name'],
                    )

        else:
            raise Exception(f"UI does not support some of the input data types: `{i['name']}` :: {i['type']}")

        # Add component to list
        gr_inp.append(tmp)

        # In case of files, the info field is not supported, so we have to add it
        # as an additional HTML component
        if i['type'] == 'file':
            tmp = gr.HTML(
                value=f'<p style="color: Gray;">{info}</p>',
                label=f"{i['name']}-info",
            )
            gr_inp.append(tmp)

    return gr_inp


def api2gr_outputs(api_out):
    """
    Transform DEEPaaS webargs to Gradio outputs.
    """
    gr_out = []
    for k, v in api_out.items():

        # Sometimes peoples use webargs.Field() when the value does not fit other
        # categories (eg. dict of dicts)
        # In those cases return a string with the value
        if 'type' not in v:
            tmp = gr.Textbox(
                type='text',
                label=k,
                )

        elif k in ['labels', 'probabilities']: # processed below
            continue

        elif v['type'] in ['string', 'boolean']:

            # Check if it is a media file (encoded in base64)
            desc = v.get('description', '').lower()
            if 'image' in desc:
                tmp = gr.Image(
                    type='filepath',
                    label=k,
                    )
            elif 'audio' in desc:
                tmp = gr.Audio(
                    type='filepath',
                    label=k,
                    )
            elif 'video' in desc:
                tmp = gr.Video(
                    label=k,
                    )

            # Otherwise return normal string
            else:
                tmp = gr.Textbox(
                    type='text',
                    label=k,
                    )

        elif v['type'] in ['integer', 'number']:
            tmp = gr.Number(
                label=k,
                )
        elif v['type'] in ['array']:
            tmp = gr.Textbox(
                label=k,
                )
        elif v['type'] in ['object']:
            tmp = gr.JSON(label=k)
        else:
            raise Exception(f"UI does not support some of the output data types: {k} [{v['type']}]")

        gr_out.append(tmp)

    # Interpret 'labels'/'predictions' keys as classification
    # FIXME: this hardcoded approach should be deprecated with DEEPaaS V3 (¿in favour of custom types?)
    # --> maybe can be fixed using 'description' in marshmallow fields
    if {'labels', 'probabilities'}.issubset(api_out.keys()):
        tmp = gr.Label(
            num_top_classes=5,
            label='classification scores',
            )
        gr_out.append(tmp)

    return gr_out


def api_call(
    *user_args: tuple,  # Gradio input args, introduced by user
    api_inp: list,  # input args expected by DEEPaaS
    gr_out: list, # output args expected by DEEPaaS
    url: str,  # DEEPaaS predict endpoint
    mime: str,  # MIME of the call
    schema: bool,  # whether the module has defined a schema for output validation
    ):

    # Remove the info gr.HTML() components that come after files (ugly but unavoidable)
    # Otherwise the info is passed to deepaas
    user_args = list(user_args)
    for k, v in enumerate(api_inp):
        if v['type'] == 'file':
            del user_args[k+1]  # removes the next component

    # Fill the params/files of the call
    params, files = {}, {}
    for k, v in enumerate(user_args):

        inp_name = api_inp[k]['name']
        inp_type = api_inp[k]['type']

        # If parameter is empty, don't send anything otherwise the call will fail
        if not v:
            continue

        # If needed, preprocess Gradio inputs to deepaas-friendly format
        if inp_type == 'integer':
            v = int(v)
        elif inp_type == 'array' and isinstance(v, str):
            v = json.loads(f'[{v}]')

        # Decide whether to add the arg to "params" or "files"
        if inp_type == 'file':
            # We try to provide the mimetype to the user whenever possible
            mtype = mimetypes.guess_type(v)[0]
            if mtype:
                fname = Path(v).stem
                files[inp_name] = (fname, open(v, 'rb'), mtype)
            else:
                files[inp_name] = open(v, 'rb')
        else:
            params[inp_name] = v

    # We also send accept as a param in case the module does different post
    # processing based on this parameter.
    # Accept is hardcoded because the user does not get to choose it.
    headers = {'accept': mime}
    params['accept'] = mime

    r = session.post(
        url=url,
        headers=headers,
        params=params,
        files=files,
        )

    # Post processing of the output to Gradio-friendly format
    if mime == 'application/json':
        rc = r.content.decode("utf-8")

        if r.status_code != 200:
            raise Exception(rc)

        rc = json.loads(rc)

        # This is probably not very general, only seems implemented in image-classification-tf
        # (and related modules)  --> remove at some point
        if rc.get('status', '') == 'error':
            raise Exception(rc['message'])

        # If schema is provided, reorder outputs in Gradio's expected order
        # and format outputs (if needed)
        if schema:
            rout = []
            for arg in gr_out:
                label = arg.label

                # Even if defined in schema, modules don't return the value.
                # Swagger does not complain, nor shouldn't we
                value = rc.get(label, None)

                # Handle classification outputs
                if label == 'classification scores':
                    rout.append(
                        dict(
                            zip(
                                rc['labels'],
                                rc['probabilities']
                                )
                            )
                        )

                # Process media files
                elif isinstance(arg, (gr.Image, gr.Audio, gr.Video)):
                    media = value.encode('utf-8')  # bytes
                    media = base64.b64decode(media)  # bytes
                    with tempfile.NamedTemporaryFile(delete=False) as fp:
                        fp.write(media)
                    rout.append(fp.name)

                # Make sure generic "webargs.Field" params are strings
                elif isinstance(arg, gr.Textbox) and arg.type=='str':
                    rout.append(str(value))

                else:
                    rout.append(value)

        else:
            # If no schema provided return everything as a JSON
            rout = rc['predictions']

    else:
        # Process non-json responses: save to file and return path
        ftype = find_filetype(mime)
        with tempfile.NamedTemporaryFile(suffix=f".{ftype}", delete=False) as fp:
            fp.write(r.content)
        rout = fp.name

    return rout


def generate_footer(metadata):
    author = metadata.get('author', '')
    if isinstance(author, list):
        author = ', '.join(author)
    footer = f"""
        <link href="https://use.fontawesome.com/releases/v5.13.0/css/all.css" rel="stylesheet">
        <b>Author(s)</b>: {author} <br>
        <b>License</b>: {metadata.get('license', '')} <br>
        <b>Summary</b>: {metadata.get('summary', '')} <br>
        <a href="https://ai4eosc.eu/">
          <div align="center">
            <img src="https://ai4eosc.eu/wp-content/uploads/sites/10/2023/01/horizontal-bg-green.png" class="ai4eosc-logo" width="200" />
          </div>
        </a>
    """
    footer = inspect.cleandoc(footer)
    return footer


def find_filetype(content_type):
    # Regex pattern to match the filetype after the slash, but not if it's a wildcard (*)
    pattern = r'/([^/*]+)$'
    match = re.search(pattern, content_type)
    if match:
        return match.group(1)
    else:
        return None
