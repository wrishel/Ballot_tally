"""Global constants for ballot_tally."""


import os
from pathlib import Path
from datetime import datetime


class GLB_globs():
    def __init__(self):
        self.proj_base = proj_base = os.path.dirname(__file__)
        self.dpi = 300
        self.highest_image_num = 300000          # November 2020 election
        self.daemon_semaphore_path = '%%%DAEMON_SEMAPHORE.%%%'
        self.tracing_sql = False
        self.TESTING = True     # Nov 2020: production in the Testing database
        self.num_barcode_process = 4
        self.path_to_images = r'D:\2020_Nov'
        fn = datetime.now().strftime('%y%m%d-%H%M%S')
        self.path_to_logs = fr'{self.path_to_images}\processing_logs/'
        self.path_to_log = fr'{self.path_to_logs}\ballot_tally{fn}.log'
        self.path_to_vote_counting_logs = self.path_to_logs
        self.path_to_vote_counting_image_log = \
            Path(fr'{self.path_to_logs}\image_log.html')
        self.path_to_vote_counting_template_dir = \
            Path(fr'{proj_base}\votes\templatesV15')
        self.path_to_rpts_out_dir = \
            Path(fr'{proj_base}\rpts')
        self.path_to_vote_counting_metadata_dir = \
            Path(fr'{proj_base}\votes\metadata')
        self.path_to_vote_counting_json_log = \
            Path(fr'{proj_base}\votes\results\ballot_results.json')
        self.path_to_results_directory = Path(fr'{proj_base}\votes\results')
        self.path_to_scratches = Path(r'C:\Users\15104\AppData\Roaming\JetBrains\PyCharm2021.1\scratches')

    def extract_precinct(self, barcode):
        """Extract precinct sequence number from HART Verity ballot barcode"""

        return barcode[5:9]
