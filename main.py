import argparse
import csv
import datetime
import logging
import os
import shutil

import piexif
from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()


def lookup_csv_tables(input_dir: str):
    table_filenames = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith(".csv") and file.startswith("Photo Details"):
                table_filenames.append(os.path.join(root, file))
    return table_filenames


def parse_date(date_str):
    date_str = date_str.lower()
    date_str = " ".join(date_str.split(" ")[1:])
    s = date_str.split(" ")
    month = 0
    month_str_to_int = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    month = month_str_to_int[s[0]]
    a = date_str.split(",")
    day = int(a[0].split(" ")[1])
    x = a[1].split(" ")
    year = int(x[0])
    time = x[1].split(":")
    hour = int(time[0])
    minute = int(time[1])
    if x[2] == "pm" and hour < 12:
        hour += 12
    if x[3] != "gmt":
        raise os.error("unknown timezone " + x[3])
    return datetime.datetime(
        year, month, day, hour, minute, tzinfo=datetime.timezone.utc
    )


def read_tables(filenames):
    file_to_creation_date = dict()
    for file in filenames:
        with open(file) as fp:
            reader = csv.reader(fp)
            for row in reader:
                if row[0].lower() == "imgname":
                    continue
                file_to_creation_date[row[0]] = parse_date(row[1])
    return file_to_creation_date


def lookup_media_files(input_dir, visit):
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            visit(os.path.join(root, file))


def update_exif(filename, date):
    if filename.lower().endswith("jp2"):
        raise Exception("JP2 files are not supported")
    with open(filename, "rb") as image_file:
        image = Image.open(filename)
        if filename.lower().endswith("heic"):
            exifData = None
        else:
            exifData = image._getexif()
        if exifData is None:
            exif_ifd = {}
            exif_dict = None
        else:
            exif_dict = piexif.load(image.info["exif"])
            exif_ifd = exif_dict["Exif"]
        stringified_date = date.strftime("%Y:%m:%d %H:%M:%S")
        exif_ifd[piexif.ExifIFD.UserComment] = "From iCloud by Oleg".encode()
        exif_ifd[piexif.ExifIFD.DateTimeOriginal] = stringified_date
        exif_ifd[piexif.ExifIFD.DateTimeDigitized] = stringified_date

        if not exif_dict:
            exif_dict = {
                "0th": {306: stringified_date},
                "Exif": exif_ifd,
                "1st": {},
                "thumbnail": None,
            }
        else:
            if "0th" in exif_dict:
                exif_dict["0th"][306] = stringified_date
        exif_dat = piexif.dump(exif_dict)
        image.save(filename, exif=exif_dat, quality=100, subsampling=0)


def move_to_target(filename, date: datetime.datetime, output_dir):
    target_dir = os.path.join(
        output_dir, str(date.year), str(date.month), str(date.day)
    )
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    shutil.move(filename, os.path.join(target_dir, os.path.basename(filename)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        help="Output directory, where pictures are going to be moved. if -o /tmp/1, then /tmp/1/2022.12/31 can be created.",
        default="./target",
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input directory, where pictures and index files will be found.",
    )
    args = parser.parse_args()
    output_dir = args.output
    input_dir = args.input

    files = lookup_csv_tables(input_dir)
    file_to_date = read_tables(files)

    def visit(file):
        try:
            filename = os.path.basename(file)
            if filename not in file_to_date:
                return
            update_exif(file, file_to_date[filename])
            move_to_target(file, file_to_date[filename], output_dir)
        except Exception:
            logging.exception(f"Error happened while processing {filename}")

    lookup_media_files(input_dir, visit)


if __name__ == "__main__":
    main()
