function doPost(e) {
  var data = JSON.parse(e.postData.contents);
  var sheet = SpreadsheetApp.openById("SHEET_ID_PLACEHOLDER").getActiveSheet();
  var ratings = data.ratings.map(function(r){ return r.theme + ": " + r.rating; }).join(", ");
  sheet.appendRow([
    new Date(),
    data.nickname,
    data.uid,
    data.country,
    data.playtime,
    data.spending,
    ratings
  ]);
  return ContentService.createTextOutput(JSON.stringify({ok:true}))
    .setMimeType(ContentService.MimeType.JSON);
}

function setup() {
  var ss = SpreadsheetApp.create("FGD Survey Responses");
  var sheet = ss.getActiveSheet();
  sheet.appendRow(["Timestamp", "Nickname", "UID", "Country", "Playtime", "Spending", "Ratings"]);
  Logger.log("Sheet ID: " + ss.getId());
}
