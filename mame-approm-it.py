#!/usr/bin/python

import os
import sys
import math
import struct

# mame-approm-it.py APPROM_PATH OUT_PATH FLASH_SIZE
#	Approm mod @ APPROM_PATH and output to OUT_PATH with specificed flash size
#		mame-approm-it.py cool.o neat/ 0x400000
# mame-approm-it.py APPROM_PATH OUT_PATH
#	Approm mod @ APPROM_PATH and oputput to OUT_PATH
#		mame-approm-it.py cool.o neat/
# mame-approm-it.py APPROM_PATH FLASH_SIZE
#	Approm mod @ APPROM_PATH output to ./ with specified flash size
#		mame-approm-it.py cool.o 0x400000
# mame-approm-it.py APPROM_PATH
#	Approm mod @ APPROM_PATH output to ./ with 2MB flash size
#		mame-approm-it.py cool.o

arg_base = 0
out_size = 0x200000
out_folder_path = "./"
byte_swap = False
file_prefix = "bank0_flash"
nop_deadly = False

cargs = sys.argv

cargs = list(filter(len, sys.argv))

def can_int(val):
    try:
        int(val, 0)
    except ValueError:
        return False
    else:
        return True

if cargs[1] == "-s":
	byte_swap = True
	arg_base = 1
elif cargs[1] == "-n":
	nop_deadly = True
	arg_base = 1
elif cargs[1] == "-sn":
	byte_swap = True
	nop_deadly = True
	arg_base = 1

in_file_path = cargs[1 + arg_base]

if len(cargs) > (arg_base + 3):
	if os.path.isdir(cargs[arg_base + 2]):
		out_folder_path = cargs[arg_base + 2]
	else:
		raise Exception("Couldn't find path '" + cargs[arg_base + 2] + "'")

	if can_int(cargs[arg_base + 3]):
		out_size = int(cargs[arg_base + 3], 0)

	if len(cargs) > (arg_base + 4):
		file_prefix = cargs[arg_base + 4]

elif len(cargs) > (arg_base + 2):
	if os.path.isdir(cargs[arg_base + 2]):
		out_folder_path = cargs[arg_base + 2]
	elif can_int(cargs[arg_base + 2]):
		out_size = int(cargs[arg_base + 2], 0)
	else:
		raise Exception("Couldn't find path '" + cargs[arg_base + 2] + "'")

def nopit(code_blob, rom_base = 0x9f000000):
	offset = 0x00
	while (offset + 0x0c) < len(code_blob):
		instruction = int.from_bytes(bytes(code_blob[offset:(offset + 4)]), "big")
		next_instruction1 = int.from_bytes(bytes(code_blob[(offset + 0x04):(offset + 0x08)]), "big")
		next_instruction2 = int.from_bytes(bytes(code_blob[(offset + 0x08):(offset + 0x0c)]), "big")

		# Needs to be:
		#	lui $t0 0x2123
		#	ori $t0 0x3333
		#	mtc0 $t0, LLAddr
		# Or:
		#	lui $t0 0x2121
		#	ori $t0 0x1111
		#	mtc0 $t0, LLAddr

		if next_instruction2 == 0x40888800:
			if (instruction == 0x3c082123 and next_instruction1 == 0x35083333):
				print("\tFound EnableDisplay use WBack @ " + hex(rom_base + offset) + ", nopping it")

				code_blob[(offset - 0x18):(offset + 0x0c)] = bytearray(0x24)

				offset += 0x08
			elif (instruction == 0x3c082121 and next_instruction1 == 0x35081111):
				print("\tFound KillDisplay use WThru @ " + hex(rom_base + offset) + ", nopping it")

				code_blob[(offset - 0x18):(offset + 0x0c)] = bytearray(0x24)

				offset += 0x08

		offset += 4

	return code_blob

def simplify_size(byte_count):
	sufixes = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")

	size_e = int(math.floor(math.log(byte_count, 1024))) if byte_count > 0 else 0
	simplified_size = round(byte_count / math.pow(1024, size_e), 2)

	return str(simplified_size) + sufixes[size_e]

def alignment_error(current_size, align_to = 0x200):
	alignment_size = align_to - (current_size % align_to)
	if alignment_size < align_to:
		return alignment_size
	else:
		return 0

def checksum(data, chunk_size = 4):
	checksum = 0x00000000

	data = bytearray(data)

	if chunk_size > 1:
		if (len(data) % chunk_size) != 0:
			for a in range(chunk_size - (len(data) % chunk_size)):
				data.append(0)

	for i in range(0, len(data), chunk_size):
		if chunk_size == 1:
			checksum += data[i]
		elif chunk_size == 2:
			checksum += (data[i] << 0x08) + (data[i + 1])
		elif chunk_size == 3:
			checksum += (data[i] << 0x10) + (data[i + 1] << 0x08) + (data[i + 2])
		elif chunk_size == 4:
			checksum += (data[i] << 0x18) + (data[i + 1] << 0x10) + (data[i + 2] << 0x08) + (data[i + 3])

	return checksum & 0xffffffff

approm_blob = bytearray(open(in_file_path, "rb").read())

start_check = int.from_bytes(bytes(approm_blob[0x00:0x03]), "big")

if start_check != 0x100000:
	print("This ROM file doesn't look right. I couldn't find 0x100000 at the start. Stopping here!")
else:
	build_size = int.from_bytes(bytes(approm_blob[0x0c:0x10]), "big") << 2
	code_size = int.from_bytes(bytes(approm_blob[0x10:0x14]), "big") << 2

	alignment_error = alignment_error(build_size, 0x80000)

	if alignment_error > 0:
		print("Build size doesn't look aligned (current=" + hex(build_size) + ", aligned=" + hex(build_size + alignment_error) + "). Setting the correct value in the header but you might need to change more to get this ROM to work.")

		struct.pack_into(
			">I",
			approm_blob,
			0x0c,
			(build_size + alignment_error) >> 2
		)

	if nop_deadly:
		print("Squasing deadly instructions")
		approm_blob[0x00:code_size] = nopit(approm_blob[0x00:code_size])

	if len(approm_blob) < code_size:
		print("File size is smaller than the code size? Stopping...")
	else:
		print("Checking code checksum")

		current_checksum = int.from_bytes(bytes(approm_blob[0x08:0x0c]))

		approm_blob[0x08:0x0c] = bytearray(0x04)
		calculated_checksum = checksum(approm_blob[0x00:code_size])

		print("\tCalculated code checksum: " + hex(calculated_checksum) + ", Current code checksum: " + hex(current_checksum))

		if calculated_checksum != current_checksum:
			print("\t\tFixing code checksum")

			approm_blob[0x08:0x0c] = bytearray(0x04)
			struct.pack_into(
				">I",
				approm_blob,
				0x08,
				calculated_checksum
			)
		else:
			print("\t\tChecksum is good!")
			struct.pack_into(
				">I",
				approm_blob,
				0x08,
				current_checksum
			)

		print("Outputting " + simplify_size(out_size) + " " + file_prefix + " files for MAME to '" + out_folder_path + "'")

		with open(out_folder_path + "/" + file_prefix + "0", "wb") as f0:
			with open(out_folder_path + "/" + file_prefix + "1", "wb") as f1:
				swap = 0
				for i in range(0, out_size, 2):
					byte1 = bytes(1)
					byte2 = bytes(1)

					if (i+1) <= len(approm_blob):
						byte1 = bytes(approm_blob[i:(i + 1)])

					if (i+2) <= len(approm_blob):
						byte2 = bytes(approm_blob[(i + 1):(i + 2)])

					f = f0
					if (swap%2) == 1:
						f = f1
					else:
						f = f0

					if byte_swap:
						f.write(byte2 + byte1)
					else:
						f.write(byte1 + byte2)

					swap += 1

				f1.close()
			f0.close()

		print("Thank you, come again!")
