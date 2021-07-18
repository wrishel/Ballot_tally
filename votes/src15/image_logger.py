import cv2
from string import Template
import base64
import logging

class ImageLogger():
    
    def __init__(self, path_to_log_file, default_shrink_percentage=15):
        #expects a Pathlib path to log file
        #if path is None, don't open a logger
        if path_to_log_file is None:
            logging.warning("NOTE: Image Logger was NOT enabled")
            self.image_logfile = None
        else:
            self.image_logfile = open(path_to_log_file, 'w') #or do we want 'a'?
            self.count_images_logged = 0
            self.default_shrink_percentage = default_shrink_percentage #range 1-100
            self._write_html_style_header()
        return
    
    def log_image(self, img, scale_percent, date, image_link_path, message ):
        if self.image_logfile is None:
            return None

        if scale_percent is None:
            scale_percent = self.default_shrink_percentage

        report_as_html = self._format_report_as_html(img, scale_percent, date, image_link_path, message)
        if report_as_html is not None:
            self._write_html_to_log(report_as_html)
            return True
        else:
            return None
        
    def close_log(self):
        if self.image_logfile is not None:
            self.image_logfile.close()
        return
    
    def _write_html_style_header(self):
        #write out some styling to enable flex layout for image / comments in a row
        output = Template(
            """
            <html>
                <head>
                    <style>
                    .flex-container {
                        display: flex;
                        justify-content: left;
                        align-items: center;
                    }
                    .flex-container > div {
                        /* width: 1500px; */
                        margin: 5px;
                        text-align: left;
                        line-height: $line_height;
                        font-size: $font_size;
                    }
                    </style>
                </head>
            <body style="background-color: #eeeaea;>
            """).substitute(line_height="16px", font_size=" 14px" ) #changes from wes to shrink sizes
        self.image_logfile.write(output)            
        return

    def _write_html_to_log(self, report_as_html ):
        #expects report_as_html to be proper HTML to append to logfile
        self.image_logfile.write(report_as_html)
        self.count_images_logged += 1
        
        #todo - add logic to open a new logfile if this one gets too big?
        
        return
    
    def _format_report_as_html(self, img, scale_percent, date, image_link_path, message):
        #hack to dump a report to running html log, using VisualRecord tool
        # inspired by (and some code used from)
        #
        # https://github.com/dchaplinsky/visual-logging
        #
        #img will be scaled by scale_factor (percent range 1 - 100)
        #OBSOLETE scan_form_name is the file name of the jpg scan
        #image_link_path is Path() to the image
        #message is text with newlines.  Newlines will be converted to <br> for html

        width = int(img.shape[1] * scale_percent / 100)
        height = int(img.shape[0] * scale_percent / 100)
        dim = (width, height)

        resized = cv2.resize(img, dim, interpolation = cv2.INTER_CUBIC)  #from wes, higher quality to comp for smaller sizes

        retval, buf = cv2.imencode(".%s" % "png", resized)
        if not retval:
            logging.error("Image Logger - FAILURE to encode image for html output - no log added")
            return None

        mime = "image/%s" % "png"

        img_encoded = Template('<img src="data:$mime;base64,$data" />').substitute(
                    mime=mime, data=base64.b64encode(buf).decode())

        message_html = ""
        for line in message.split('\n'):
            message_html += line
            message_html += "<br>"

        #dpm 13Dec2020 - added test for absolute image_link_path, otherwise .as_uri() will throw ValueError
        #just do a resolve and hope for the best?
        if image_link_path is not None and image_link_path != "":
            abs_link_path = image_link_path.resolve() #convert to absolute path
            abs_link_path_uri = abs_link_path.as_uri()
        else:
            abs_link_path_uri = ""

        output = Template(
            """
            <hr style="height:4px;border-width:0;color:gray;background-color:gray">
            <div class="flex-container">
                <div>
                    <a href=$image_link>
                        $img
                    </a>
                </div>
                <div>
                    <b>Form:&nbsp;</b>$form_name<br>
                    <b>Date:&nbsp;</b>$date<br>
                    <b>Message:</b><br>$message<br>
                </div>
            </div>
            """).substitute(image_link=abs_link_path_uri, 
                        img=img_encoded, form_name=image_link_path.stem, date=date, message=message_html)

        return(output)