from datetime import datetime

import requests
from jinja2 import Environment, FileSystemLoader
from chart_generator import ui_metrics_chart
from email.mime.image import MIMEImage
from email_notifications import Email


class UIEmailNotification(object):

    def __init__(self, arguments):
        self.test_id = arguments['test_id']
        self.gelloper_url = arguments['galloper_url']
        self.gelloper_token = arguments['token']
        self.galloper_project_id = arguments['project_id']
        self.report_id = arguments['report_id']
        self.test_name = arguments['test']

    def ui_email_notification(self):
        info = self.__get_test_info()
        last_reports = self.__get_last_report(info['name'], 5)
        tests_data = []
        for each in last_reports:
            results_info = self.__get_results_info(each["uid"])
            tests_data.append(results_info)
        t_comparison = []
        for index, test in enumerate(tests_data):
            aggregated_test_data = {}
            for metric in ["total_time", "tti", "fvc", "lvc"]:
                if metric == "total_time":
                    _arr = [each[metric] * 1000 for each in test]
                else:
                    _arr = [each[metric] for each in test]
                aggregated_test_data[metric] = int(sum(_arr) / len(_arr))
            aggregated_test_data["date"] = last_reports[index]["start_time"][2:-3]
            aggregated_test_data["report"] = f"{self.gelloper_url}/visual/report?report_id={last_reports[index]['id']}"
            t_comparison.append(aggregated_test_data)
        user_list = self.__extract_recipient_emails(info)

        date = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        subject = f"[UI] Test results for {info['name']}. From {date}."

        report_info = self.__get_report_info()
        results_info = self.__get_results_info(self.report_id)
        for each in results_info:
            print(f"Results - {each}")
            each["report"] = f"{self.gelloper_url}{each['report']}"

        status = "PASSED"
        if not report_info['passed']:
            status = "FAILED"

        t_params = {
            "scenario": report_info['name'],
            "start_time": report_info["start_time"],
            "status": status,
            "duration": report_info['duration'],
            "env": report_info['environment'],
            "browser": report_info['browser'].capitalize(),
            "version": report_info['browser_version'],
            "view_port": "1920x1080",
            "loops": report_info["loops"],
            "pages": len(results_info)
        }
        email_body = self.__get_email_body(t_params, results_info, t_comparison)

        charts = []
        charts.append(self.create_ui_metrics_chart(t_comparison))

        return Email(self.test_name, subject, user_list, email_body, charts, date)

    def __extract_recipient_emails(self, info):
        return info['emails'].split(',')

    def __get_test_info(self):
        return self.__get_url(
            f"/tests/{self.galloper_project_id}/frontend/{self.test_id}?raw=1")

    def __get_last_report(self, name, count):
        return self.__get_url(f"/observer/{self.galloper_project_id}?name={name}&count={count}")

    def __get_report_info(self):
        return self.__get_url(f"/observer/{self.galloper_project_id}?report_id={self.report_id}")

    def __get_results_info(self, report_id):
        return self.__get_url(f"/visual/{self.galloper_project_id}/{report_id}?order=asc")

    def __get_email_body(self, t_params, results_info, t_comparison):
        env = Environment(
            loader=FileSystemLoader('./templates'))
        template = env.get_template("ui_email_template.html")
        return template.render(t_params=t_params, results=results_info, t_comparison=t_comparison)

    def __get_url(self, url):
        resp = requests.get(
            f"{self.gelloper_url}/api/v1{url}", headers={
                'Authorization': f'bearer {self.gelloper_token}',
                'Content-type': 'application/json'
            })

        if resp.status_code != 200:
            raise Exception(f"Error {resp}")

        return resp.json()

    @staticmethod
    def create_ui_metrics_chart(builds):
        labels, x, total_time, tti, fvc, lvc = [], [], [], [], [], []
        count = 1
        for test in builds:
            labels.append(test['date'])
            total_time.append(round(test['total_time'], 2))
            tti.append(round(test['tti'], 2))
            fvc.append(round(test['fvc'], 2))
            lvc.append(round(test['lvc'], 2))
            x.append(count)
            count += 1
        datapoints = {
            'title': 'UI metrics',
            'label': 'UI metrics',
            'x_axis': 'Test Runs',
            'y_axis': 'Time, ms',
            'width': 14,
            'height': 4,
            'path_to_save': '/tmp/ui_metrics.png',
            'total_time': total_time[::-1],
            'tti': tti[::-1],
            'fvc': fvc[::-1],
            'lvc': lvc[::-1],
            'values': x,
            'labels': labels[::-1]
        }
        ui_metrics_chart(datapoints)
        fp = open('/tmp/ui_metrics.png', 'rb')
        image = MIMEImage(fp.read())
        image.add_header('Content-ID', '<ui_metrics>')
        fp.close()
        return image
