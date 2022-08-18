from flask import Flask, request, jsonify
from TTS.utils.synthesizer import Synthesizer
from TTS.utils.manage import ModelManager
import subprocess
import requests
import os
import os.path
import json
import asyncio
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from textwrap import wrap
import fnmatch

from tweetcapture import TweetCapture
from flask import send_from_directory, make_response
from mutagen.mp3 import MP3
from pydub import AudioSegment
from flask_cors import CORS
from werkzeug.utils import secure_filename
from bson.json_util import dumps, loads
import requests
import urllib.request
from bson.objectid import ObjectId
import uuid

from tweet import GenTweet


from pymongo import MongoClient
client = MongoClient("mongodb://localhost:27017/")
db = client['amphitweet']
usercol = db["users"]
videocol = db["videos"]


app = Flask(__name__)
CORS(app)
load_dotenv()


bearer_token = os.getenv("BEARER_TOKEN")



def create_url(tweetid):
    tweet_fields = "tweet.fields=text,created_at,public_metrics&expansions=author_id&user.fields=username,profile_image_url"
    # Tweet fields are adjustable.
    # Options include:
    # attachments, author_id, context_annotations,
    # conversation_id, created_at, entities, geo, id,
    # in_reply_to_user_id, lang, non_public_metrics, organic_metrics,
    # possibly_sensitive, promoted_metrics, public_metrics, referenced_tweets,
    # source, text, and withheld
    ids = "ids="+tweetid
    # You can adjust ids to include a single Tweets.
    # Or you can add to up to 100 comma-separated IDs
    url = "https://api.twitter.com/2/tweets?{}&{}".format(ids, tweet_fields)
    username = "usernames=yazzzat"
    user_fields = "user.fields=username,id,profile_image_url"

    return url


def bearer_oauth(r):
    """
    Method required by bearer token authentication.
    """

    r.headers["Authorization"] = f"Bearer {bearer_token}"
    r.headers["User-Agent"] = "v2TweetLookupPython"
    return r


def connect_to_endpoint(url):
    response = requests.request("GET", url, auth=bearer_oauth)
    print(response.status_code)
    if response.status_code != 200:
        raise Exception(
            "Request returned an error: {} {}".format(
                response.status_code, response.text
            )
        )
    return response.json()


@app.route("/create_video", methods=["POST"])
def create_video():
    data = request.get_json()
    url = "http://localhost:3000/out/" + \
        data["filename"]

    urllib.request.urlretrieve(url, "video/"+data["filename"])

    yoid = ObjectId(data["userid"])

    user = usercol.find_one({"_id": yoid})

    x = videocol.insert_one(
        {"userid": data["userid"], "filename": data["filename"], "caption": data["caption"], "username": user["username"], "profilepic": user["profile"], "likes": 0})

    id = {
        "message": "success"
    }
    # Add to mongo [ caption , userid , filename]

    return jsonify(id)

# upload video from client


@app.route("/custom_video", methods=["POST"])
def upload_video():
    file = request.files['file']
    data = json.loads(request.form.get('data'))
    print(file, data)

    file.filename = str(uuid.uuid4())+".mp4"
    file.save("video/"+file.filename)
    yoid = ObjectId(data["userid"])

    user = usercol.find_one({"_id": yoid})
    x = videocol.insert_one(
        {"userid": data["userid"], "filename": file.filename, "caption": data["caption"], "username": user["username"], "profilepic": user["profile"], "likes": 0})

    return jsonify({"message": "success"})


@app.route("/bro")
def bro():
    return "hi"


@app.route("/signup", methods=["POST"])
def create_user():
    data = json.loads(request.form.get('data'))
    print(request)
    file = request.files['file']
    print(data, file)
    ext = file.filename
    print(ext)
    ext = ext.split(".")[-1]
    print(ext)

    
    m = usercol.find_one({"username": data["username"]})
    print(m)
    if m:
        id = {
            "id": str(m["_id"])
        }

        return jsonify(id)
    else:
        o=ObjectId()
        so=str(o)
        x = usercol.insert_one(
            {"_id":o,"username": data["username"], "password": data["password"],"profile":so})

        id = {
            "id": str(x.inserted_id)
        }
        fn=str(x.inserted_id)
        fnext=fn+"."+ext
        
        file.save("profile/"+secure_filename(fnext))

        return jsonify(id)


@app.route("/getallvids", methods=["GET"])
def getallvids():
    x = videocol.find({})
    response = []
    for i in x:
        i["_id"] = str(i["_id"])
        response.append(i)

    return response


@app.route("/getmyvids/<path:path>")
def getmyvids(path):
    x = videocol.find({"userid": path})
    response = []
    for i in x:
        i["_id"] = str(i["_id"])
        response.append(i)

    return response

# increment likes for video


@app.route("/like/<path:path>")
def like(path):
    yoid = ObjectId(path)
    x = videocol.find_one({"_id": yoid})
    x["likes"] = x["likes"] + 1
    y = videocol.update_one({"_id": yoid}, {"$set": x})
    return jsonify({"message": "success"})


# delete video from mongo
@app.route("/delete/<path:path>")
def delete(path):
    yoid = ObjectId(path)
    x = videocol.delete_one({"_id": yoid})

    return jsonify({"message": "success"})


@app.route('/video/<path:path>')
def send_video(path):
    return send_from_directory('video', path)


@app.route('/profile2/<path:path>')
def send_profile(path):
    print(path)
    path =path+"*"
    d = fnmatch.filter(os.listdir("profile"), path)
    print(path)
    return send_from_directory('profile', d[0])

@app.route('/profile/<path:path>')
def send_profile1(path):
    
    return send_from_directory('profile', path)


@app.route('/audio/<path:path>')
def send_audio(path):

    voice = (path.split('/')[-1])
    path = path.split('/')[0]
    tweetid = path.split(".")[0]
    print(path)
    oo = "audio/"+(path)
    if os.path.isfile(oo):
        audio = AudioSegment.from_file("audio/{}".format(path))
        duration = audio.duration_seconds
        duration = round(duration)
        response = make_response(send_from_directory('audio', path))

        response.headers['time'] = (duration)
        return response
    else:

        modelname = 'tts_models/en/vctk/vits'

        manager = ModelManager()
        model_path, config_path, model_item = manager.download_model(modelname)
        synthesizer = Synthesizer(model_path, config_path)

        url = create_url(tweetid)
        json_response = connect_to_endpoint(url)
        tweet = json_response["data"][0]["text"]

        if voice == "female1":
            wav = synthesizer.tts(tweet, 'p245')
            path1 = 'audio/'+tweetid+'.mp3'
            synthesizer.save_wav(wav, path1)
        elif voice == "female2":
            wav = synthesizer.tts(tweet, 'p246')
            path1 = 'audio/'+tweetid+'.mp3'
            synthesizer.save_wav(wav, path1)
        elif voice == "male1":
            wav = synthesizer.tts(tweet, 'p241')
            path1 = 'audio/'+tweetid+'.mp3'
            synthesizer.save_wav(wav, path1)
        elif voice == "male2":
            wav = synthesizer.tts(tweet, 'p269')
            path1 = 'audio/'+tweetid+'.mp3'
            synthesizer.save_wav(wav, path1)

        audio = AudioSegment.from_file("audio/{}".format(path))
        duration = audio.duration_seconds
        duration = round(duration)
        response = make_response(send_from_directory('audio', path))

        response.headers['time'] = (duration)
        return response


@app.route('/tweet/<path:path>')
def send_tweet(path):
    print(path)
    if os.path.isfile("tweet/"+path):
        return send_from_directory('tweet', path)
    else:

        

        tweetid = path.split(".")[0]
        print(tweetid)
        url = create_url(tweetid)
        json_response = connect_to_endpoint(url)
        tweet = json_response["data"][0]["text"]
        username = json_response["includes"]["users"][0]["username"]
        name = json_response["includes"]["users"][0]["name"]
        twid=json_response["data"][0]["id"]
        png=json_response["includes"]["users"][0]["profile_image_url"]
        userid = json_response["includes"]["users"][0]["id"]
        urllib.request.urlretrieve(png,"profile/"+userid+".jpg" )
        likes = json_response["data"][0]["public_metrics"]["like_count"]
        retweet = json_response["data"][0]["public_metrics"]["retweet_count"]
        reply = json_response["data"][0]["public_metrics"]["reply_count"]
        created_at = json_response["data"][0]["created_at"]
        print(json_response)
        print(created_at)
        
        

        gt = GenTweet(text=tweet, imPath="profile/"+userid+".jpg", name=name, username=username, isVerified=True,userid=twid,likes=likes,retweet=retweet,reply=reply,created_at=created_at)
        gt.CreateTweet()

        return send_from_directory('tweet', twid+".png")





@app.route('/tts', methods=['POST'])
def tts():
    fromclient = request.get_json()
    print(type(fromclient))
    for tweet in fromclient.values():
        command = "tts --text %s --model_name 'tts_models/en/vctk/vits' --out_path output/speak.mp3 --speaker_idx p261" % (
            tweet)

        subprocess.call(command, shell=True)
        #print(f"{subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True).decode()}")
    return '<h1>Hello, World!</h1>'


@app.route('/tts1', methods=['POST'])
def tts1():
    fromclient = request.get_json()
    modelname = 'tts_models/en/vctk/vits'

    manager = ModelManager()
    model_path, config_path, model_item = manager.download_model(modelname)
    synthesizer = Synthesizer(model_path, config_path)

    tweety = TweetCapture()

    tweetid = fromclient['tweetid']
    voice = fromclient['voice']
    url = create_url(tweetid)
    json_response = connect_to_endpoint(url)
    tweet = json_response["data"][0]["text"]

    if voice == "female1":
        wav = synthesizer.tts(tweet, 'p261')
        path1 = 'audio/'+tweetid+'.mp3'
        synthesizer.save_wav(wav, path1)
    elif voice == "female2":
        wav = synthesizer.tts(tweet, 'p262')
        path1 = 'audio/'+tweetid+'.mp3'
        synthesizer.save_wav(wav, path1)
    elif voice == "male1":
        wav = synthesizer.tts(tweet, 'p263')
        path1 = 'audio/'+tweetid+'.mp3'
        synthesizer.save_wav(wav, path1)
    elif voice == "male2":
        wav = synthesizer.tts(tweet, 'p264')
        path1 = 'audio/'+tweetid+'.mp3'
        synthesizer.save_wav(wav, path1)

    picurl = "https://twitter.com/" + \
        json_response["includes"]["users"][0]["username"]+"/status/"+tweetid

    asyncio.run(tweety.screenshot(
        picurl, "tweet/"+tweetid+".png", mode=3, night_mode=2))

    return "success"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port='5000',debug=True)
