This repo should be a tool to check client process status, retrieve information about them, and if they fail in different status than finished, take the log, and cut the information that contains (each log line should contain process_uuid so its easy to retrieve those lines). If it is finished, retrieve the onedrive video and a report. So, the task to accomplish this are:

1) Create a connection with the db to retrieve last processes (maybe use the view we already have)? With the view or table of processes run in the last 24h, we are going to check if there is a failed process. We also take the finished processes. What I mean, we retrieve all 24h information processes. Maybe we can avoid having the folders_2_client txt in the pc, as we are doing this query directly to the db now?

2) We retrieve the logs for the failed processes. We send it over the gmail attached? Maybe upload it to the onedrive and give a link?
2.1) We retrieve the video link (onedrive) and the report from the API. We have still to figure how to generate this report. The best idea is to create a front that calls the API and generates the report for us

3) We generate the mail with all the info obtained