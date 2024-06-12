# This is the file that is ran from Nomad, when we launch a "try-it" job from PAPI

git clone https://github.com/ai4os/deepaas_ui
cd deepaas_ui
pip install -r requirements.txt
nohup deep-start --deepaas &
python launch.py --api_url http://0.0.0.0:5000/ --ui_port 8000
# TODO: add command to kill after 10 minutes