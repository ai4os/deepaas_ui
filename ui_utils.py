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

"""
File where we moved some functions to declutter launch.py
"""

import inspect

import gradio as gr


def api2gr_inputs(api_inp):
    """
    Transform DEEPaaS webargs to Gradio inputs.
    """
    inp_names = [i['name'] for i in api_inp]
    inp_types = {i['name']: i['type'] for i in api_inp}
    media_types = {}
    gr_inp = []
    for k, v in zip(inp_names, api_inp):
        if 'enum' in v.keys():
            tmp = gr.inputs.Dropdown(choices=v['enum'],
                                     default=v.get('default', None),
                                     label=k)  # could also be gr.inputs.Radio()
        elif v['type'] in ['integer', 'number']:
            if (v['type'] == 'integer') and {'minimum', 'maximum'}.issubset(v.keys()):
                tmp = gr.inputs.Slider(default=v.get('default', None),
                                       minimum=v.get('minimum', None),
                                       maximum=v.get('maximum', None),
                                       step=1,
                                       label=k)
            else:
                tmp = gr.inputs.Number(default=v.get('default', None),
                                       label=k)
        elif v['type'] in ['boolean']:
            tmp = gr.inputs.Checkbox(default=v.get('default', None),
                                     label=k)
        elif v['type'] in ['string']:
            tmp = gr.inputs.Textbox(default=v.get('default', None),
                                    label=k)
        elif v['type'] in ['array']:
            tmp = gr.inputs.Textbox(default=v.get('default', None),
                                    label=k)
        elif v['type'] in ['file']:
            desc = v.get('description', '').lower()
            if 'image' in desc:
                media_types[k] = 'image'
                tmp = gr.inputs.Image(optional= not v['required'],
                                      type='file',
                                      label=k)
            elif 'audio' in desc:
                media_types[k] = 'audio'
                tmp = gr.inputs.Audio(source='upload',  # maybe sometimes it makes more sense to use 'microphone'
                                      optional= not v['required'],
                                      type='file',
                                      label=k)
            elif 'video' in desc:
                media_types[k] = 'video'
                tmp = gr.inputs.Video(optional= not v['required'],
                                      type=None,
                                      label=k)
            else:
                raise Exception(
                    f"""
                    You should include the media type in the `{k}` arg description.
                    Supported media types: image, video, audio.
                    """)

        else:
            raise Exception(f"UI does not support some of the input data types: `{k}` :: {v['type']}")
        gr_inp.append(tmp)

    return gr_inp, inp_names, inp_types, media_types



def api2gr_outputs(struct):
    """
    Transform DEEPaaS webargs to Gradio outputs.
    """
    gr_out = []
    for k, v in struct.items():

        if k in ['labels', 'probabilities']:  # FIXME: remove in the future, see below
            continue

        if v['type'] in ['string', 'boolean']:

            # Check if it is media files (encoded in base64)
            desc = v.get('description', '').lower()
            if 'image' in desc:
                tmp = gr.outputs.Image(type='file',
                                       label=k)
            elif 'audio' in desc:
                tmp = gr.outputs.Audio(type='file',
                                       label=k)
            elif 'video' in desc:
                tmp = gr.outputs.Video(type='mp4',
                                       label=k)
            # Normal string
            else:
                tmp = gr.outputs.Textbox(type='str',
                                         label=k)

        elif v['type'] in ['integer', 'number']:
            tmp = gr.outputs.Textbox(type='number',
                                     label=k)
        elif v['type'] in ['array']:
            tmp = gr.outputs.Textbox(type='str',
                                     label=k)
        elif v['type'] in ['object']:
            tmp = gr.outputs.JSON(label=k)
        else:
            raise Exception(f"UI does not support some of the output data types: {k} [{v['type']}]")
        gr_out.append(tmp)

    # Interpret 'labels'/'predictions' keys as classification
    # FIXME: this hardcoded approach should be deprecated with DEEPaaS V3 (¿in favour of custom types?)
    # --> maybe can be fixed using 'description' in marshmallow fields
    if {'labels', 'probabilities'}.issubset(struct.keys()):
        tmp = gr.outputs.Label(num_top_classes=5,
                               type='confidences',
                               label='classification scores')
        gr_out.append(tmp)

    return gr_out


def generate_footer(metadata):
    footer = f"""
        <link href="https://use.fontawesome.com/releases/v5.13.0/css/all.css" rel="stylesheet">
        <b>Author</b>: {metadata.get('author', '')} <br>
        <b>License</b>: {metadata.get('license', '')} <br>
        <b>Summary</b>: {metadata.get('summary', '')} <br>
        <a href="https://deep-hybrid-datacloud.eu/">
          <div align="center">
            <img src="https://ai4eosc.eu/wp-content/uploads/sites/10/2022/09/horizontal-transparent.png" alt="logo" width="200"/>
          </div>
        </a>
    """
    footer = inspect.cleandoc(footer)
    return footer
