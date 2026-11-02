# Setup

## Before launching

- Register for Fannie Mae's disclosure files (PoolTalk, and its SFTP site
  for the files) and Freddie Mac's secured data site, accepting each
  agency's terms for your firm.
- Arrange a location that serves the files you download, unchanged and
  under the agencies' own file names, over HTTPS: for example
  `FNM_MF_202611.zip`, `FNM_REMIC_202611_25.zip`, `fd261105.zip` and
  `wj261105.zip`. A bearer token is supported if the location asks for one.
  The plugin reads Fannie Mae's monthly security factor file and REMIC
  factor files, and Freddie Mac's monthly security core file and 55-day,
  Gold and 75-day REMIC tranche factor files.

## After launching

1. Open the plugin's **Settings**: enter **Files location** (the folder's
   HTTPS address) and, if it asks for one, **Files location token**.
2. On the dashboard's **Data sources** page, license `fannie_mae` and
   `freddie_mac` and entitle the plugins that read factors.
3. Check its **Summary**: Connection reads Answering once the location
   answers.

Factors are read when a pool or class is first asked for, and checked daily
after that; each GSE publishes on the fourth business day of the month.
