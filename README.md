# AutoSCP
This Python application automatically transfers files to a remote server via SCP. Files with names containing today's date (YYYYMMDD) will not be transferred.


V1_2 update: Added a field for users to enter the server password, allowing the use of the AutoSCP application without needing to set up an SSH key.
V1_3 update: File transfers now exclude filenames containing today's date (YYYYMMDD). For example, on June 11, 2025, a file named 20250611_Mu_data.txt will not be transferred.
