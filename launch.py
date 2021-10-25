import json

import click
import gradio as gr
import requests


@click.command()
@click.option('--api_url',
              default='http://0.0.0.0:5000/',
              help='URL of the DEEPaaS API')
@click.option('--ui_port',
              default=8000,
              help='URL of the deployed UI')
def main(api_url, ui_port):

#     # Configuration
#     api_url = 'http://0.0.0.0:5000/'
#     ui_port = 8000 

    # Parse api inference inputs/outputs
    sess = requests.Session()
    r = sess.get(api_url + 'swagger.json')
    specs = r.json()
    pred_paths = [p for p in specs['paths'].keys() if p.endswith('predict/')]

    p = pred_paths[0]  # FIXME: we are only doing this for the first model found
    api_inp = specs['paths'][p]['post']['parameters']
    api_out = specs['paths'][p]['post']['produces']

    # Transform api data types to Gradio data types
    names = [i['name'] for i in api_inp]
    gr_inp = []
    for i in api_inp:
        if 'enum' in i.keys():
            tmp = gr.inputs.Dropdown(choices=i['enum'],
                                     label=i['name'])  # could also be checkbox
        gr_inp.append(tmp)

    outtypes_map = {'application/json': 'json'}
    gr_out = [outtypes_map[i] for i in api_out]


    def api_call(*args, **kwargs):

        headers = {'accept': api_out[0]}
        params = dict(zip(names, args))

        r = sess.post(api_url + p, 
                      headers=headers,
                      params=params,
                      verify=False)
        r = r.content.decode("utf-8")  # FIXME: this probably has to be adapted for non-json returns
        return r

    # Launch Gradio interface
    iface = gr.Interface(
        fn=api_call, 
        inputs=gr_inp,
        outputs=gr_out,
        server_name="0.0.0.0",
        server_port=ui_port,
    )

    iface.launch(debug=True)  #FIXME: remove debug for production


if __name__ == '__main__':
    main()
