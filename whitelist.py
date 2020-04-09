#! /usr/bin/env python3

import sqlite3
import sys
import time
import tg

def canPunish(api,gid):
    tmp = api.query('getChatMember',{'chat_id':gid,'user_id':api.info['id']})
    return tmp['status'] == 'creator' or ('can_restrict_members' in tmp and tmp['can_restrict_members'] and 'can_delete_messages' in tmp and tmp['can_delete_messages'])

def processItem(message,db,api):
    if 'message' not in message:
        return
    deleteMe = False
    req = db.cursor()
    resp = req.execute("SELECT time FROM blacklist WHERE user=? AND gid=?",(message['message']['from']['id'],message['message']['chat']['id'])).fetchone()
    if resp:
        if int(resp[0]) >= message['message']['date']:
            deleteMe = True
        else:
            req.execute("DELETE FROM blacklist WHERE user=? AND gid=?",(message['message']['from']['id'],message['message']['chat']['id']))
            db.commit()
    if not deleteMe and 'text' in message['message'] and message['message']['text']:
        # Process bot command
        if message['message']['text'][0] == '/':
            stripText = message['message']['text'].split(' ',1)[0]
            if '@'+api.info['username'] in stripText:
                stripText=stripText[:-len(api.info['username'])-1]
                stripText = stripText.lower()
            if stripText == '/ping':
                api.sendMessage(message['message']['chat']['id'],'Hell o\'world! It took '+str(time.time()-message['message']['date'])+' seconds!',{'reply_to_message_id':message['message']['message_id']})
            elif stripText == '/join':
                parseMsg = message['message']['text'].split('\n')
                reqParam = parseMsg[0].split(' ')
                if len(reqParam) != 2:
                    api.sendMessage(message['message']['chat']['id'],"Usage: \n<pre>/join &lt;group name&gt;\n&lt;reason for your request to join&gt;</pre>",{'reply_to_message_id':message['message']['message_id'],'parse_mode':'HTML'})
                else:
                    req = db.cursor()
                    resp = req.execute("SELECT gid FROM config WHERE alias=?",(reqParam[1],)).fetchone()
                    if not resp:
                        api.sendMessage(message['message']['chat']['id'],"Error: Group "+reqParam[1]+" is supported by us. Please contact their admin.",{'reply_to_message_id':message['message']['message_id']})
                    else:
                        gid = resp[0]
                        resp = bool(req.execute("SELECT count(user) FROM whitelist WHERE user=? and gid=?",(message['message']['from']['id'],gid)).fetchone()[0])
                        if resp:
                            api.sendMessage(message['message']['chat']['id'],"You already has the permission to join the group "+reqParam[1]+".",{'reply_to_message_id':message['message']['message_id']})
                        else:
                            resp = bool(req.execute("SELECT count(user) FROM application WHERE user=? and gid=?",(message['message']['from']['id'],gid)).fetchone()[0])
                            if resp:
                                req.execute("UPDATE application SET time=?, comment=? WHERE user=? AND gid=?",(int(time.time()),parseMsg[1] if len(parseMsg) > 1 else "None"))
                            else:
                                req.execute("INSERT INTO application VALUES (?,?,?,?)",(int(time.time()),message['message']['from']['id'],gid,parseMsg[1] if len(parseMsg)>1 else "None"))
                            db.commit()
                            api.sendMessage(message['message']['chat']['id'],"Your application to join group "+reqParam[1]+" has been recorded in our system.",{'reply_to_message_id':message['message']['message_id']})
    ### Now we need permission to deal with join and msg
    if not canPunish(api,message['message']['chat']['id']):
        return
    if 'new_chat_members' in message['message']:
        if 'from' in message['message']:
            userStatus = api.query('getChatMember',{'user_id':message['message']['from']['id'],'chat_id':message['message']['chat']['id']})
            if reqUser['status'] in ['creator','administrator']:
                return
        for newMember in message['message']['new_chat_members']:
            if newMember['id'] != api.info['id'] and ('is_bot' not in newMember or not newMember['is_bot']):
                print('Checking whitelist')
                req = db.cursor()
                inWhitelist = bool(req.execute("SELECT count(user) FROM whitelist WHERE gid=? AND user=?",(message['message']['chat']['id'],newMember['id'])).fetchone()[0])
                if not inWhitelist:
                    try:
                        api.query('kickChatMember',{'until_date':int(time.time())+120,'chat_id':message['message']['chat']['id'],'user_id':newMember['id']})
                        req.execute("INSERT INTO blacklist VALUES (?,?,?)",(int(time.time())+5,message['message']['chat']['id'],newMember['id']))
                        db.commit()
                        deleteMe = True
                    except tg.APIError:
                        pass
    if deleteMe:
        try:
            api.query('deleteMessage',{'chat_id':message['message']['chat']['id'],'message_id':message['message']['message_id']})
        except tg.APIError:
            pass

def run(db,api):
    batch = api.query('getUpdates')
    lastID = None
    for item in batch:
        processItem(item,db,api)
        lastID = item['update_id']
    while True:
        batch = api.query('getUpdates',{'offset':lastID+1,'timeout':20}) if lastID is not None else api.query("getUpdates",{'timeout':20})
        for item in batch:
            processItem(item,db,api)
            lastID = item['update_id']

def main(args):
    dbFile = args[0]
    apiKey = args[1]
    db = sqlite3.connect(dbFile)
    api = tg.tgapi(apiKey)
    run(db,api)

if __name__ == '__main__':
    main(sys.argv[1:])
