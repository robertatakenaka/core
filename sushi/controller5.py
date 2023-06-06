import os
import json
import logging
import csv
from datetime import datetime
from time import sleep


SUSHI_URI = "http://usage.apis.scielo.org"


def extract_data(data):
    """
    http://usage.apis.scielo.org/reports/ir_a1?begin_date=2022-05-01&end_date=2022-05-31&pid=S0074-02762000000300004&api=v2

    {
       "Report_Header": {
          "Created": "2023-05-10T19:06:53.891314",
          "Created_By": "Scientific Electronic Library Online SUSHI API",
          "Customer_ID": "",
          "Report_ID": "ir_a1",
          "Release": 5,
          "Report_Name": "Journal Article Requests",
          "Institution_Name": "",
          "Institution_ID": [
             {
                "Type": "ISNI",
                "Value": ""
             }
          ]
       },
       "Report_Filters": [
          {
             "Name": "Begin_Date",
             "Value": "2022-05-01"
          },
          {
             "Name": "End_Date",
             "Value": "2022-05-31"
          }
       ],
       "Report_Attributes": [
          {
             "Name": "Attributes_To_Show",
             "Value": "Data_Type|Access_Method"
          }
       ],
       "Exceptions": [],
       "Report_Items": [
          {
             "Item": "10.1590/S0074-02762000000300004",
             "Publisher": "Instituto Oswaldo Cruz, Ministério da Saúde",
             "Publisher_ID": [],
             "Platform": "Scientific Electronic Library Online - Brasil",
             "Authors": "",
             "Publication_Date": "",
             "Article_Version": "",
             "DOI": "10.1590/S0074-02762000000300004",
             "Proprietary_ID": "",
             "Print_ISSN": "",
             "Online_ISSN": "",
             "URI": "",
             "Parent_Title": "Memórias do Instituto Oswaldo Cruz",
             "Parent_DOI": "",
             "Parent_Proprietary_ID": "",
             "Parent_Print_ISSN": "0074-0276",
             "Parent_Online_ISSN": "1678-8060",
             "Parent_URI": "",
             "Parent_Data_Type": "Journal",
             "Item_ID": [
                "3wMhTnYTfPK3qsT4SqVcFMH"
             ],
             "Data_Type": "Article",
             "Access_Type": "Open Access",
             "Access_Method": "Regular",
             "Performance": [
                {
                   "Period": {
                      "Begin_Date": "2022-05-01",
                      "End_Date": "2022-05-31"
                   },
                   "Instance": {
                      "Metric_Type": "Total_Item_Requests",
                      "Count": "4"
                   }
                },
                {
                   "Period": {
                      "Begin_Date": "2022-05-01",
                      "End_Date": "2022-05-31"
                   },
                   "Instance": {
                      "Metric_Type": "Unique_Item_Requests",
                      "Count": "4"
                   }
                }
             ]
          }
       ]
    }

    """
    resp = None
    for item in data.get("Report_Items") or []:
        resp = {
            "Item": item["Item"],
            "DOI": item["DOI"],
            "Parent_Print_ISSN": item["Parent_Print_ISSN"],
            "Parent_Online_ISSN": item["Parent_Online_ISSN"],
        }
        for id_ in item["Item_ID"]:
            if '-' in id_:
                resp["pid_v2"] = id_
            else:
                resp["pid_v3"] = id_
        break

    x = {}
    Unique_Item_Requests = {}
    for item in data.get("Report_Items") or []:
        print(item)
        print("")
        for performance in item["Performance"]:
            metric_type = performance["Instance"]["Metric_Type"]

            begin_date = performance["Period"]["Begin_Date"]
            end_date = performance["Period"]["End_Date"]
            print(performance)
            print("")
            x.setdefault((begin_date, end_date), {})
            count = int(performance["Instance"]["Count"])
            x[(begin_date, end_date)][metric_type] = count
            print(x)
            print("")

    for k, v in x.items():
        r = resp.copy()
        r.update({"begin_date": k[0], "end_date": k[1]})
        r.update(v)
        print(r)
        yield r


def get_yearly_access_data_uri(pid, year):
    """
    Obtém URI de um artigo em um dado ano

    Parameters
    ----------
    pid : str PID
    year : str YYYY

    """
    uri = (
        f"{SUSHI_URI}/reports/ir_a1?"
        f"begin_date={year}-01-01&"
        f"end_date={year}-12-31&"
        f"pid={pid}&api=v2"
    )
    return {"uri": uri, "pid": pid, "suffix": year}


def get_daily_access_data_uri(pid, day):
    """
    Obtém URI de um artigo em um dado dia

    Parameters
    ----------
    pid : str PID
    day : str (YYYY-MM-DD)

    http://usage.apis.scielo.org/reports/ir_a1?
    begin_date=2022-05-01&end_date=2022-05-31&pid=&api=v2
    """
    return (
        f"{SUSHI_URI}/reports/ir_a1?"
        f"begin_date={day}&"
        f"end_date={day}&"
        f"pid={pid}&api=v2"
    )


# def get_sushi_data(uri):
#     """
#     Obtém os dados de acessos

#     Parameters
#     ----------
#     uri : str

#     """
#     try:
#         response = requests.get(uri)
#         yield from extract_data(response)
#     except Exception as e:
#         yield {
#             "error": f"Unable to get sushi data for {uri} {e}",
#             "sushi-uri": uri,
#         }


# def get_begin_date(availability_date):
#     year = availability_date[:4]
#     month = availability_date[4:6]
#     day = availability_date[:-2]
#     return year, month, day

def get_uri_for_day(pid, year):
    for m in range(1, 13):
        for d in range(1, 31):
            try:
                day = datetime(int(year), m, d)
            except Exception as e:
                logging.error(e)
                continue
            else:
                day = day.isoformat()[:10]

            yield {"uri": get_daily_access_data_uri(pid, day), "pid": pid, "suffix": day}


def get_sushi_uris(pid_list, year):
    for pid in pid_list:
        yield get_yearly_access_data_uri(pid, year)


def create_wget(items, output_dir):
    for item in items:
        uri = item["uri"]
        pid = item["pid"]
        suffix = item["suffix"]
        yield f'wget "{uri}" -O {output_dir}/{pid}-{suffix}.json'


# def get_yearly_access_numbers(pid_list, year, collection_url):
#     for pid in pid_list:
#         uri = get_yearly_access_data_uri(pid, year)
#         rows = get_sushi_data(uri)
#         for row in rows:
#             row["pid"] = pid
#             row["harvest-date"] = datetime.now().isoformat()
#             row['link'] = f"{endpoint}{pid}"
#             yield row

# def read_downloaded_files(pid_list, output_dir, collection_url):
#     for json_file in sorted(os.listdir(output_dir), key=os.path.getmtime):
#         with open(os.path.join(output_dir, json_file)) as fp:
#             try:
#                 response = fp.read()
#                 rows = extract_data(json.loads(response))
#             except Exception as e:
#                 yield {"error": str(e), "response": response}
#             else:
#                 for row in rows:
#                     row["pid"] = pid
#                     row["harvest-date"] = datetime.now().isoformat()
#                     row['link'] = f"{endpoint}{pid}"
#                     yield row


def read_downloaded_files(pid_list, output_dir, endpoint):
    for filename in os.listdir(output_dir):
        pid = filename.split("-2022")[0]
        file_path = os.path.join(output_dir, filename)
        print("")
        print(filename)
        with open(file_path) as fp:
            try:
                response = fp.read()
                rows = extract_data(json.loads(response))
                for row in rows:
                    row["pid"] = pid
                    row["harvest-date"] = datetime.now().isoformat()
                    row["link"] = f"{endpoint}{pid}"
                    print(row)
                    yield row
            except Exception as e:
                raise
                logging.info(e)
                yield {
                    "pid": pid,
                    "harvest-date": datetime.now().isoformat(),
                    "link": f"{endpoint}{pid}",
                    "filename": file_path,
                    "error": str(e),
                    "response": response,
                }


def get_pid_list(input_file_path):
    with open(input_file_path) as fp:
        for item in fp.readlines():
            yield item.strip()


def save_result(rows, file_path):
    fieldnames = [
        "DOI",
        "Total_Item_Requests",
        "Unique_Item_Requests",
        "begin_date",
        "end_date",
        "link",
        "pid_v2",
        "pid_v3",
        "Item",
        "Parent_Print_ISSN",
        "Parent_Online_ISSN",
        "pid",
        "harvest-date",
        "error",
        "sushi-uri",
        "response",
        "filename",
    ]

    with open(file_path, "w") as fp:
        fp.write("")

    with open(file_path, "w") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def create_wget_script(pid_list, year, output_dir, script):
    uris = get_sushi_uris(pid_list, year)
    with open(script, "w") as fp:
        fp.write("\n".join(create_wget(uris, output_dir)))


if __name__ == "__main__":
    input_file_path = "acesso.1516-1846.2022.txt"
    output_dir = "sushi-1516-1846-2022/2022"
    year = "2022"
    endpoint = "http://www.scielo.br/scielo.php?script=sci_arttext&pid="
    output_file_path = "acesso.1516-1846.2022.csv"

    pid_list = get_pid_list(input_file_path)
    # create_wget_script(
    #     pid_list=pid_list,
    #     year=year,
    #     output_dir=output_dir,
    #     script="acesso.1516-1846.2022.wget.sh"
    # )

    rows = read_downloaded_files(pid_list, output_dir, endpoint)
    save_result(rows, output_file_path)
