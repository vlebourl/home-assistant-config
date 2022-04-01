import appdaemon.plugins.hass.hassapi as hass
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import shelve

class GSheets(hass.Hass):
  def initialize(self):
     self.log("GSheets started")
     runtime = datetime.datetime.now()
     addseconds = (round((runtime.minute*60 + runtime.second)/self.args["RunEverySec"])+1)*self.args["RunEverySec"]
     runtime = runtime.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(seconds=addseconds)
     self.run_every(self.publish_to_gs,runtime,self.args["RunEverySec"]) 

  def publish_to_gs(self,kwargs):
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('/config/google_credentials.json', scope)
    client = gspread.authorize(creds)
    fmt = '%Y-%m-%d %H:%M:%S'
    d = datetime.datetime.now()
    d_string = d.strftime(fmt)


    spreadSheet = client.open_by_url("https://docs.google.com/spreadsheets/d/12s5Wf-88wwiM7tnnn57qFgDjdWqnCCaN3kythySw4jM/edit?usp=sharing") #client.open(self.args["SpreadSheetName"])
    uploadJson = self.args["upload"] #json string

    shelveDevice_db = shelve.open(self.args["shelveFile"])

    old_data = 0#shelveDevice_db[nameInShelve]
    for option in uploadJson:
      sheet = (spreadSheet.add_worksheet(
          title=option["sheetName"], rows="100", cols="10") if
               (self.__checkSheetsCreated(spreadSheet,
                                          option["sheetName"]) == False) else
               spreadSheet.worksheet(option["sheetName"]))
      entityState = self.get_state(option["entity"])
      nameInSheet = option["nameInSheet"]
      nameInShelve = option["sheetName"]+'_'+nameInSheet

      if (old_data != entityState):
           row = [d_string,nameInSheet,entityState]
           index = 2
           sheet.insert_row(row, index, value_input_option='USER_ENTERED')
           shelveDevice_db[nameInShelve] = entityState

    shelveDevice_db.close()

     

  def __checkSheetsCreated(self,spreadSheet,sheetName):
    #output a list of all the sheets in a document
    listWorkSheets = spreadSheet.worksheets()

    return any((sheetName == workSheet.title) for workSheet in listWorkSheets)