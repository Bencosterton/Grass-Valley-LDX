# Grass Valley LDK Gateway Control

This repository contains an implementation for sending commands to Grass Valley LDK Gateway camera systems using XML.
You can run the Flask web apllication on your network with will handle device discovery, issueing commands, checking on devices etc.
Or use the bellow command exmaples to build your own worklow.

![image](https://github.com/user-attachments/assets/7a582f88-ce06-4f6c-91e9-1ab1ac327c6c)


## Overview

The Grass Valley LDK Gateway uses an XML-based protocol for communication. 
Steps;

1. Authenticate with the gateway
2. Send control command using the same socket connection

## XML Protocol Details

### Authentication

Before sending any commands, authentication is required:

**Authentication Request:**
```xml
<?xml version="2.0" encoding="UTF-8"?>
<application-authentication-request xml-protocol="2.0">
  <name>TallySender</name>
</application-authentication-request>
```

**Authentication Response:**
```xml
<request-response result="Ok" />
<application-authentication-indication xml-protocol="2.0">
  <supported-xml-protocol>1.1</supported-xml-protocol>
  <supported-xml-protocol>2.0</supported-xml-protocol>
  <name>SYSTEM-NAME</name>
  <location>SYSTEM-LOCATION</location>
</application-authentication-indication>
```

### Tally Control Commands

After successful authentication, control commands can be sent using the same socket connection:

**Turn Red Tally ON:**
```xml
<?xml version="2.0" encoding="UTF-8"?>
<function-value-change>
  <device>
    <sessionid>9VDA4O</sessionid>
    <function id="8215">
      <Value>1</Value>
    </function>
  </device>
</function-value-change>
```

**Turn Red Tally OFF:**
```xml
<?xml version="2.0" encoding="UTF-8"?>
<function-value-change>
  <device>
    <sessionid>9VDA4O</sessionid>
    <function id="8215">
      <Value>0</Value>
    </function>
  </device>
</function-value-change>
```

Also it could be useful to check the status of a tally, maybe?:

**Is Red Tally ON:**
```xml
<?xml version="2.0" encoding="UTF-8"?>
<function-value-request>
  <device>
	<deviceid>XCU-09</deviceid>
	<function id="8215">
	</function>
  </device>
</function-value-request>
```

**Response:**
```xml
<request-response result="Ok" />
<function-value-indication>
  <device>
	<sessionid>9VDA4O</sessionid>
	<name>9</name>
	<alias>ST1-CAM9</alias>
	<deviceid>XCU-09</deviceid>
	<type>Basestation</type>
	<function id="8215" blocked="false">
  	<value>0</value>
	</function>
  </device>
</function-value-indication>
```


## Function IDs

Check the GV_Function_IDs.txt file for full list of Basestation, Camera, and OCP functions_id's

https://github.com/Bencosterton/Grass-Valley-LDX/blob/main/GV_Function_IDs.txt

## Implementation Details

1. **XML Version**: Use XML version 2.0 in the declaration
2. Depedning the the function, a sessionid, or deviceid can be used. Need to do more research here.
3. **Socket Connection**: Maintain the same socket connection between authentication and commands

## Usage for web app

-Install requirments

```bash
pip install -r requirements.txt
```
- Run the Flaks app
```bash
python3 gv_command_server.py
```
- Enter your GV Gateway IP on the 'Config' page (I assume your using port 8080), then 'Save Configuraiton' > 'Authenticate Now' > 'Discover Devices'
