##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2013-2021 Sven Bursch-Osewold
##               2021-2022 Roland Noell  
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
##

'''
A decoder for DCC-Signals (operate model railways digitally):
All telegrams are currently interpreted according to RCN standard.
The timing can be interpreted according to RCN and NMRA. 
The decoding of DCC is done by measuring the time interval
of the zero crossings (edge changes). Therefore a high sampling
rate is necessary for an accurate measurement. With sampling
rates below 1MHz the decoding can be inaccurate depending
on the signal quality. For compliance testing min. 2MHz.

Features:
- Decoding of individual packets
- Consideration of speed mode (CV29)
- Evaluation adjustable for operation/service mode
- Adjustable offset for interpretation accessory addresses

- Search functions for
-- accessory address (specify address in decimal)
-- decoder address (specify address in decimal)
-- CV (specify CV in decimal)
-- single byte ('and' linked if address or CV filled)
--- (e.g. 3, 0xFF, 0b01101001)
-- command (searches commands in textform)
--- (e.g. pom, basic acc)
-- usage: 
   1. enter value
   2. press 'zoom to fit'-button, 
   3. search for occurrences
   4. zoom to occurrence

- Different timing modes adjustable
-- NMRA/RCN decoding: 
   Acts like a decoder with according timing
-- NMRA/RCN compliance testing: 
   Tests the signal at the output of a command station
   according to NMRA/RCN timing
   (no Railcom cutout allowed)
-- Experimental: 
--- user adjustable values for tests
--- possibility to compare timings:
    For the detection the values of the selected mode
    as well as the set experimental values are used
    and the difference is displayed

- 'RCN/Exp. mode: allow/reject streched 0-bits'
- 'compliance mode: min. preamble bits':
  in decoder mode fixed to 10 bits
- 'ignore pulse <= 4 µs':
   short pulses are ignored
   (what would the signal look like without the short pulse?)

- No decoding of packet sequences (e.g. programming mode)
- No evaluation of the preamble length for packet detection
- Rudimentary decoding of register and page mode packets
- RailComPlus® system commands not decoded (as not documented)
- Used settings for timing in the different modes: 
  See file pd.py, below comment '## used settings for timing'.

Used norms:
RCN 210, 211, 212, 213, 214, 216, 217, 218
(NMRA s-9.2, s-9.2.1 Draft, s-9.2.1.1 Draft, s-9.2.3, s-9.3.2)
http://www.vhdm.de
https://www.nmra.org

RailCom® (Lenz Elektronik GmbH,Gießen)
RailComPlus® (Lenz Elektronik GmbH,Gießen, ESU electronic solutions,Ulm)
'''

from .pd import Decoder

