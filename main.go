package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/mdp/qrterminal/v3"
	"go.mau.fi/whatsmeow"
	waProto "go.mau.fi/whatsmeow/binary/proto"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
	"google.golang.org/protobuf/proto"
	_ "modernc.org/sqlite"
)

type MyClient struct {
	WAClient       *whatsmeow.Client
	eventHandlerID uint32
}

type Config struct {
	PhoneNumbers []string
	HotWords     []string
	Author       string
}

func (mycli *MyClient) register() {
	mycli.eventHandlerID = mycli.WAClient.AddEventHandler(mycli.eventHandler)
}

// contains checks if a string is in an array of strings
func contains(arr []string, str string) bool {

	// if the array is empty, return true
	if len(arr) == 0 {
		return true
	}

	for _, a := range arr {
		if a == str {
			return true
		}
	}
	return false
}

// pHones := make(map[string]bool)

func readConfig() map[string]bool {
	// read the JSON file
	file, err := ioutil.ReadFile("config.json")
	if err != nil {
		fmt.Println("Error reading file:", err)
		return nil
	}

	// define a struct to hold the JSON data
	type jsonData struct {
		PhoneNumbers []string `json:"phoneNumbers"`
		hotWord      []string `json:"hotWord"`
		Author       string   `json:"author"`
	}

	// unmarshal the JSON data into the struct
	var data jsonData
	err = json.Unmarshal(file, &data)
	if err != nil {
		fmt.Println("Error unmarshalling JSON:", err)
		return nil
	}

	// create a map of phone numbers
	phones := make(map[string]bool)
	for _, number := range data.PhoneNumbers {
		phones[number] = true
	}
	return phones
}

func readConfigx() Config {
	// Read the config file
	file, err := os.Open("config.json")
	if err != nil {
		fmt.Println("Error opening config file:", err)
	}
	defer file.Close()
	decoder := json.NewDecoder(file)
	config := Config{}
	err = decoder.Decode(&config)
	if err != nil {
		fmt.Println("Error decoding config file:", err)
	}
	return config
}

func (mycli *MyClient) eventHandler(evt interface{}) {
	phones := readConfig()

	// phoneNumbers := cfgData.PhoneNumbers
	switch v := evt.(type) {
	case *events.Message:
		newMessage := v.Message

		if v.Info.IsFromMe || v.Info.IsGroup {
			fmt.Println("skip nomor dan skip chat di grup")
			return

		}

		checkSender := phones[v.Info.Sender.User]
		fmt.Println("check sender")
		fmt.Println(v.Info.Sender.User)
		fmt.Println(checkSender)

		if !checkSender {
			fmt.Println("tak kenal. skip nomor.")
			// return
		}
		msg := newMessage.GetConversation()
		msg_raw := newMessage.GetExtendedTextMessage()
		//kirim status available
		mycli.WAClient.SendPresence(types.PresenceAvailable)

		fmt.Println("GetConversation : ", msg)
		fmt.Println("Sender : ", v.Info.Sender)
		fmt.Println("Sender Number : ", v.Info.Sender.User)
		fmt.Println("is from me : ", v.Info.IsFromMe)
		fmt.Println("IsGroup : ", v.Info.IsGroup)
		fmt.Println("MessageSource : ", v.Info.MessageSource)
		fmt.Println("ID : ", v.Info.ID)
		fmt.Println("Media ID : ", v.Info.MediaType)
		fmt.Println("PushName : ", v.Info.PushName)
		fmt.Println("BroadcastListOwner : ", v.Info.BroadcastListOwner)

		fmt.Println("Message from - Conv:", v.Info.Sender.User, "->", msg)
		fmt.Println("---------------------->", msg)
		if msg == "" {
			msg = msg_raw.GetText()
		}

		userJid := types.NewJID(v.Info.Sender.User, types.DefaultUserServer)
		go replyChat(msg, v.Info.Sender.User, userJid, mycli)
	}
}

func sleepThenTyping(userJid types.JID, mycli *MyClient) {
	time.Sleep(3 * time.Second)
	mycli.WAClient.SendChatPresence(userJid,
		types.ChatPresenceComposing, types.ChatPresenceMediaText)
}

func replyChat(prompt string, sender string, userjid types.JID, mycli *MyClient) {

	params := url.Values{}
	params.Add("q", prompt)
	params.Add("user", sender)
	query := params.Encode()

	// Step 2 in a Goroutine
	go sleepThenTyping(userjid, mycli)

	url := "http://localhost:5001/chat?" + query
	resp, err := http.Get(url)

	// kalau kirim presense disini, bakal lama dan typing nya singkat poll

	if err != nil {
		fmt.Println("Error making request:", err)

		// stop send "typing ..." info
		time.Sleep(1 * time.Second)
		mycli.WAClient.SendChatPresence(userjid,
			types.ChatPresencePaused, types.ChatPresenceMediaText)

		response := &waProto.Message{Conversation: proto.String("an error occured.\nresend last chat please")}
		// fmt.Println("Response:", response)
		mycli.WAClient.SendMessage(context.Background(), userjid, "", response)
		return
	}

	//diam dulu 1 detik biar lebih manuasiawi, heheheh
	// time.Sleep(1 * time.Second)
	//diam dulu 2 detik biar lebih manuasiawi, heheheh

	// Read the response
	buf := new(bytes.Buffer)
	buf.ReadFrom(resp.Body)
	//kirim status sedang mengetik

	newMsg := buf.String()
	respons := strings.Split(newMsg, "\n\n")
	output := make([]string, 0)

	for _, element := range respons {
		trimmed := strings.TrimSpace(element)
		if trimmed != "" {
			output = append(output, trimmed)
		}
	}

	// its kinda weird if the chatbot give u short answer
	// but it still "typing .." and turned out no further respons.
	// short response deserve "early stop typing" special treatment.

	totalLetters := 0
	for _, s := range output {
		totalLetters += len(s)
	}

	time.Sleep(3 * time.Second)
	// if prompt == "refresh" || totalLetters <= 50

	if totalLetters <= 50 {
		mycli.WAClient.SendChatPresence(userjid,
			types.ChatPresencePaused, types.ChatPresenceMediaText)
	}

	// stop send "typing ..." info
	mycli.WAClient.SendChatPresence(userjid,
		types.ChatPresencePaused, types.ChatPresenceMediaText)

	for i := range output {

		response := &waProto.Message{Conversation: proto.String(string(output[i]))}
		// fmt.Println("Response:", response)
		mycli.WAClient.SendMessage(context.Background(), userjid, "", response)
	}
}

func main() {
	dbLog := waLog.Stdout("Database", "DEBUG", true)
	// Make sure you add appropriate DB connector imports, e.g. github.com/mattn/go-sqlite3 for SQLite
	container, err := sqlstore.New("sqlite", "file:examplestore.db?_foreign_keys=on", dbLog)
	if err != nil {
		panic(err)
	}
	// If you want multiple sessions, remember their JIDs and use .GetDevice(jid) or .GetAllDevices() instead.
	deviceStore, err := container.GetFirstDevice()
	if err != nil {
		panic(err)
	}
	clientLog := waLog.Stdout("Client", "DEBUG", true)
	client := whatsmeow.NewClient(deviceStore, clientLog)
	// add the eventHandler
	mycli := &MyClient{WAClient: client}
	mycli.register()

	if client.Store.ID == nil {
		// No ID stored, new login
		qrChan, _ := client.GetQRChannel(context.Background())
		err = client.Connect()
		if err != nil {
			panic(err)
		}
		for evt := range qrChan {
			if evt.Event == "code" {
				// Render the QR code here
				// e.g. qrterminal.GenerateHalfBlock(evt.Code, qrterminal.L, os.Stdout)
				// or just manually `echo 2@... | qrencode -t ansiutf8` in a terminal
				qrterminal.GenerateHalfBlock(evt.Code, qrterminal.L, os.Stdout)
				//				fmt.Println("QR code:", evt.Code)
			} else {
				fmt.Println("Login event:", evt.Event)
			}
		}
	} else {
		// Already logged in, just connect
		err = client.Connect()
		if err != nil {
			panic(err)
		}
	}

	// Listen to Ctrl+C (you can also do something else that prevents the program from exiting)
	c := make(chan os.Signal)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	<-c

	client.Disconnect()
}
