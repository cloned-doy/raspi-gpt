## raspi/gpt-app
this repo is for backup only.

basically is a ChatGPT powered chatbot that runs on raspi. the code used to run 'normally-perfectly' on my raspberrypi 3B+ as the 'server'. just trust me for this claims wkwk.

it has 2 main file written in golang and python: main.go for serving the whatsapp chat, then passed the chat to xserver.py which powered by reverse-engineered (unofficial) ChatGPT API.

due to unmaintained issue, the main.go and the xserver.py may not be able to run anymore. but still, hope you able to read and get the ideas behind the code.

## how to
the main.go file has been compiled as go-whatsapp-raspi-arm7. while it runs on the raspi, it will asks for whatsapp QR code login, and create a sqlite database file to store the login creds and chat history.


