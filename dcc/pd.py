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
Used norms:
RCN-210 (01.12.2019)
RCN-211 (10.09.2021)
RCN-212 (06.12.2020)
RCN-213 (27.07.2015)
RCN-214 (10.09.2021)
RCN-216 (17.12.2017)
RCN-217 (01.12.2019)
RCN-218 (10.09.2021)
'''

import sigrokdecode as srd

class SamplerateError(Exception):
    pass
    
class ConfigParamError(Exception):
    pass

class Ann:
    BITS, BITS_OTHER, FRAME, FRAME_OTHER, DATA, DATA_ACC, DATA_DEC, DATA_CV, COMMAND, INFO, ERROR, VARIANCE1, VARIANCE2, SEARCH_ACC, SEARCH_DEC, SEARCH_CV, SEARCH_BYTE, SEARCH_COMMAND = range(18)

class Decoder(srd.Decoder):
    api_version = 3
    id          = 'dcc'
    name        = 'DCC'
    longname    = 'Digital Command Control'
    desc        = 'DCC protocol (operate model railways digitally)'
    license     = 'gplv2+'
    inputs      = ['logic']
    outputs     = []
    tags        = ['Encoding']
    
    ##software version of DCC decoder
    version     = '3.0.0'

    ## used settings for timing 
    ## half1BitMin, half1BitMax, max1BitTolerance, half0BitMin, half0BitMax, half0BitMaxStreched
    timing = [  [0,  0,  0,  0,  0,     0],      #invalid
                [52, 64, 6,  90, 10000, 10000],  #NMRA decoding
                [52, 64, 6,  90, 119,   10000],  #RCN decoding
                [55, 61, 3,  95, 9900,  9900],   #NMRA compliance testing
                [55, 61, 3,  95, 116,   9900],   #RCN compliance track
                [56, 60, 3,  97, 114,   9898],   #RCN compliance station
                [0,  0,  0,  0,  0,     0]    ]  #Experimental
    BIT1MIN      =0
    BIT1MAX          =1
    BIT1TOLERANCE        =2
    BIT0MIN                  =3
    BIT0MAX                      =4
    BIT0MAXSTRECHED                     =5

    RAILCOMCUTOUTMIN     = 454 #The railcom cutout is 0 volt between a positive and negative voltage. Before the signal analyzer 
    RAILCOMCUTOUTMAX     = 488 #the voltage is rectified and therefore one edge is lost. The timing should still work.
    BIT0MAXSTRECHEDTOTAL = 12000
    #BIT0MAXSTRECHEDTOTAL = 9000 #todo
    minCountPreambleBits = 10

    maxInterferingPulseWidth = 4 #µs (ignoreInterferingPulse)

    timingINVALID        = 0
    timingNMRAdecoder    = 1
    timingRCNdecoder     = 2
    timingNMRAcompliance = 3
    timingRCNcomplianceT = 4
    timingRCNcomplianceS = 5
    timingExperimental   = 6
    timingModeNo         = timingINVALID

    B1min                  = 0
    B1max                  = 0
    B1tolerance            = 0
    B0min                  = 0
    B0max                  = 0
    B0max_streched         = 0
    ExpAccurancy           = -1

    channels    = (
        {'id': 'data', 'name': 'D0', 'desc': 'Data line'},
    )
    annotations = (
        ('bits1',     'Bits'),
        ('bits2',     'Other'),
        ('frame1',    'Frame'),
        ('frame2',    'Other'),
        ('data1',     'Data'),
        ('data2',     'Accessory address'),
        ('data3',     'Decoder address'),
        ('data4',     'CV'),
        ('command',   'Command'),
        ('info',      'Info'),
        ('error',     'Error'),
        ('variance1', 'Variance (compare)'),
        ('variance2', 'Variance (compare)'),
        ('search1',   'Accessory address'),
        ('search2',   'Decoder address'),
        ('search3',   'CV'),
        ('search4',   'Byte'),
        ('search5',   'Command'),
    )
    annotation_rows = (
        ('bits_',     'Bits',         (Ann.BITS, Ann.BITS_OTHER,)),
        ('frame_',    'Frame',        (Ann.FRAME, Ann.FRAME_OTHER,)),
        ('data_',     'Data/Command', (Ann.DATA_ACC, Ann.DATA_DEC, Ann.DATA_CV, Ann.DATA,)),
        ('command_',  'Command/Key',  (Ann.COMMAND,)),
        ('info_',     'Info',         (Ann.INFO,)),
        ('error_',    'Error',        (Ann.ERROR,)),
        ('variance_', 'Variance',     (Ann.VARIANCE1, Ann.VARIANCE2,)),
        ('search_',   'Search',       (Ann.SEARCH_ACC, Ann.SEARCH_DEC, Ann.SEARCH_CV, Ann.SEARCH_BYTE, Ann.SEARCH_COMMAND,)),
    )
    options = (
        {'id': 'CV_29_1',                 'desc': 'CV29 Bit 1',                                   'default': '1: 28/128 speed mode', 'values': ('1: 28/128 speed mode', '0: 14 speed mode') },
        {'id': 'Mode_112_127',            'desc': 'address 112-127',                              'default': 'operation mode', 'values': ('operation mode', 'service mode') },
        {'id': 'Addr_offset',             'desc': 'accessory address offset',                     'default': 0 },
        {'id': 'Search_acc_addr',         'desc': 'search accessory address [decimal]',           'default': '' },
        {'id': 'Search_dec_addr',         'desc': 'search decoder address [decimal]',             'default': '' },
        {'id': 'Search_cv',               'desc': 'search CV [decimal]',                          'default': '' },
        {'id': 'Search_byte',             'desc': 'search byte [dec/0b/0x] (e.g. 3, 0xFF)',       'default': '' },
        {'id': 'Search_command',          'desc': 'search command [text] (e.g. DCC-A)',           'default': '' },
        {'id': 'Timing_mode',             'desc': 'timing mode',                                  'default': 'NMRA decoding', 'values': ('NMRA decoding', 'RCN decoding', 'NMRA compliance testing', 'RCN compliance testing track', 'RCN compliance testing station', 'Experimental') },
        {'id': 'RCN_allow_streched_zero', 'desc': 'RCN/Exp mode: allow streched 0-bits',          'default': 'no', 'values': ('no', 'yes') },
        {'id': 'Preamble_bits_count',     'desc': 'compliance mode: min. preamble bits',          'default': 17 },
        {'id': 'Ignore_short_pulse',      'desc': 'ignore pulse <= '+str(maxInterferingPulseWidth)+' µs', 'default': 'no', 'values': ('no', 'yes') },
        {'id': 'B1min',                   'desc': 'Experimental:1-bit half min. [µs]',            'default': 52, },
        {'id': 'B1max',                   'desc': 'Experimental:1-bit half max. [µs]',            'default': 64, },
        {'id': 'B1tolerance',             'desc': 'Experimental:1-bit half tolerance [µs]',       'default': 6, },
        {'id': 'B0min',                   'desc': 'Experimental:0-bit half min. [µs]',            'default': 90, },
        {'id': 'B0max',                   'desc': 'Experimental:0-bit half max. [µs] (RCN+Exp.)', 'default': 119, },
        {'id': 'B0max_streched',          'desc': 'Experimental:0-bit half streched [µs]',        'default': 10000, },
        {'id': 'Timing_compare',          'desc': 'Experimental:compare timing: mode/exp.',       'default': 'off', 'values': ('off', 'on') },
        #{'id': 'ExpAccurancy',            'desc': 'Exp:Accuracy variance [µs] (<0=auto)',         'default': -1, },
    )

    weekday = ['Monday',    #0
               'Tuesday',   #1
               'Wednesday', #2
               'Thursday',  #3
               'Friday',    #4
               'Saturday',  #5
               'Sunday'     #6
              ]
    weekday_short = ['Mo', #0
                     'Tu', #1
                     'We', #2
                     'Th', #3
                     'Fr', #4
                     'Sa', #5
                     'Su'  #6
                    ]
    month = ['?',     #0
             'Jan. ', #1
             'Feb. ', #2
             'Mar. ', #3
             'Apr. ', #4
             'Mai ',  #5
             'Jun. ', #6
             'Jul. ', #7
             'Aug. ', #8
             'Sep. ', #9
             'Oct. ', #10
             'Nov. ', #11
             'Dec. '  #12
            ]
            
    def crc_calc(self, data):
        result = 0
        if (data & 1): result ^= 0x5e
        if (data & 2): result ^= 0xbc
        if (data & 4): result ^= 0x61
        if (data & 8): result ^= 0xc2
        if (data & 0x10): result ^= 0x9d
        if (data & 0x20): result ^= 0x23
        if (data & 0x40): result ^= 0x46
        if (data & 0x80): result ^= 0x8c
        return result
    
    def CRC(self, packetByte):
        crc_value = 0
        for i in range (0, len(packetByte)-1 -1):
            crc_value = self.crc_calc(packetByte[i][0] ^ crc_value)
        return crc_value
            
    def processCRC(self, pos, packetByte):
        if pos+1 >= len(packetByte)-1:
            self.put_packetbytes(packetByte, 0, len(packetByte)-1,     [Ann.ERROR, ['CRC or Checksum missing', 'Error', 'E']])
        else:
            pos, error = self.incPos(pos, packetByte)
            if error == True: return pos, True
            commandText1 = 'CRC'
            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1]])
            crcByte = packetByte[pos][0]
            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [hex(crcByte)]])
            crcCalculated = self.CRC(packetByte)
            if crcByte == crcCalculated:
                output_1 = 'OK'
                self.put_packetbyte(packetByte, pos,     [Ann.FRAME, ['CRC: ' + output_1, output_1]])
            else:
                output_1 = hex(crcByte) + '<>' + hex(crcCalculated)
                self.put_packetbytes(packetByte, 0, len(packetByte)-2, [Ann.ERROR, ['CRC false', 'Error', 'E']])
                self.put_packetbyte(packetByte, pos,     [Ann.FRAME_OTHER, ['CRC: ' + output_1, output_1]])
        return pos, False
            
    def putx(self, start, end, data):
        self.put(start, end, self.out_ann, data)
        
    def put_signal(self, data):
        self.put(self.edge_1, self.edge_3, self.out_ann, data)
        
    def put_packetbyte(self, packetByte, pos, data):
        self.put(packetByte[pos][1][0], packetByte[pos][1][8], self.out_ann, data)
        
    def put_packetbytes(self, packetByte, start, end, data):
        self.put(packetByte[start][1][0], packetByte[end][1][8], self.out_ann, data)
    
    def __init__(self):
        self.reset()

    def reset(self):
        #This function is called before the beginning of the decoding. This is the place to reset variables internal to your protocol decoder to their initial state, such as state machines and counters.
        self.dccStart               = 0
        self.dccLast                = 0
        self.dccBitCounter          = 0
        self.dccBitPos              = []
        self.dccValue               = 0
        self.decodedBytes           = []
        self.dccStatus              = 'SYNCRONIZESIGNAL'
        self.half1Counter           = 0
        self.syncSignal             = True
        self.lastPacketWasStop      = False
        self.railcomCutoutPossible  = False
        self.broken1bitPossible     = False
        self.speed14                = False
        self.serviceMode            = False
        self.addrOffset             = 0
        self.ignoreInterferingPulse = 'no'
        self.timingCompare          = 'off'
        self.timingMode             = 'NMRA decoding'
        self.timingModeNo           = self.timingINVALID
        self.rcnAllowStrechedZero   = 'no'
        self.accuracy               = 0

    def start(self):
        #This function is called before the beginning of the decoding. This is the place to register() the output types, check the user-supplied PD options for validity, and so on.
        self.out_ann = self.register(srd.OUTPUT_ANN)

        ##############
        #read and verify options
        self.AddrOffset             = self.options['Addr_offset']
        self.timingMode             = self.options['Timing_mode']
        self.rcnAllowStrechedZero   = self.options['RCN_allow_streched_zero']
        self.preambleBitsCount      = self.options['Preamble_bits_count']
        self.ignoreInterferingPulse = self.options['Ignore_short_pulse']
        self.timingCompare          = self.options['Timing_compare']
        self.command_search         = self.options['Search_command']
        
        if self.timingMode == 'NMRA decoding':
            self.timingModeNo         = self.timingNMRAdecoder
            self.minCountPreambleBits = 10
        elif self.timingMode == 'RCN decoding':
            self.timingModeNo         = self.timingRCNdecoder
            self.minCountPreambleBits = 10
        elif self.timingMode == 'NMRA compliance testing':
            if self.samplerate < 2000000:
                self.timingModeNo = self.timingINVALID
            else:
                self.timingModeNo = self.timingNMRAcompliance
            self.minCountPreambleBits = self.preambleBitsCount
        elif self.timingMode == 'RCN compliance testing track':
            if self.samplerate < 2000000:
                self.timingModeNo = self.timingINVALID
            else:
                self.timingModeNo = self.timingRCNcomplianceT
            self.minCountPreambleBits = self.preambleBitsCount
        elif self.timingMode == 'RCN compliance testing station':
            if self.samplerate < 2000000:
                self.timingModeNo = self.timingINVALID
            else:
                self.timingModeNo = self.timingRCNcomplianceS
            self.minCountPreambleBits = self.preambleBitsCount
        elif self.timingMode == 'Experimental':
            self.timingModeNo = self.timingExperimental
            self.minCountPreambleBits = 10

        if self.options['CV_29_1']      == '0: 14 speed mode':
            self.speed14     = True

        if self.options['Mode_112_127'] == 'service mode':
            self.serviceMode = True
        
        try:
            self.acc_addr_search = int(self.options['Search_acc_addr'])
        except:
            self.acc_addr_search = -255
        if self.acc_addr_search < 1 or self.acc_addr_search > 2048:
            self.acc_addr_search = -255
        
        try:
            self.dec_addr_search = int(self.options['Search_dec_addr'])
        except:
            self.dec_addr_search = -255
        if self.dec_addr_search < 0 or self.dec_addr_search > 10239:
            self.dec_addr_search = -255
        
        try:
            self.cv_addr_search  = int(self.options['Search_cv'])
        except:
            self.cv_addr_search  = -255
        if self.cv_addr_search < 1 or self.cv_addr_search > 16777216:
            self.cv_addr_search = -255

        try:
            self.byte_search = int(self.options['Search_byte'], base=10)
        except:
            try:
                self.byte_search = int(self.options['Search_byte'], base=2)
            except:
                try:
                    self.byte_search = int(self.options['Search_byte'], base=16)
                except:
                    self.byte_search = -255
        if self.byte_search < 0 or self.byte_search > 255:
            self.byte_search = -255
        
        try:
            self.B1min  = int(self.options['B1min'])
        except:
            self.B1min  = -255
        try:
            self.B1max  = int(self.options['B1max'])
        except:
            self.B1max  = -255
        try:
            self.B1tolerance  = int(self.options['B1tolerance'])
        except:
            self.B1tolerance  = -255
        try:
            self.B0min  = int(self.options['B0min'])
        except:
            self.B0min  = -255
        try:
            self.B0max  = int(self.options['B0max'])
        except:
            self.B0max  = -255
        try:
            self.B0max_streched  = int(self.options['B0max_streched'])
        except:
            self.B0max_streched  = -255
        try:
            self.ExpAccurancy  = int(self.options['ExpAccurancy'])
        except:
            self.ExpAccurancy  = -255
            
        self.timing[self.timingExperimental][self.BIT1MIN]         = self.B1min
        self.timing[self.timingExperimental][self.BIT1MAX]         = self.B1max
        self.timing[self.timingExperimental][self.BIT1TOLERANCE]   = self.B1tolerance
        self.timing[self.timingExperimental][self.BIT0MIN]         = self.B0min
        self.timing[self.timingExperimental][self.BIT0MAX]         = self.B0max
        self.timing[self.timingExperimental][self.BIT0MAXSTRECHED] = self.B0max_streched

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def incPos(self, pos, packetByte):
        #Support function: Returns next position of packet if position exists
        if pos+1 < len(packetByte):
            return pos+1, False
        else:
            self.put_packetbyte(packetByte, pos, [Ann.ERROR, ['Byte missing at next position: ' + str(pos+2), 'Error', 'E']])
            return pos, True  #avoid access violation
            
    def handleDecodedBytes(self, packetByte):
        validPacketFound = False
        acc_addr         = -1  #found accessory address
        dec_addr         = -1  #found decoder address
        cv_addr          = -1  #found CV

        if len(packetByte) < 3:
            self.put_packetbytes(packetByte, 0, len(packetByte)-1, [Ann.ERROR, ['Paket too short: ' + str(len(packetByte)) + ' Byte only', 'Error', 'E']])
            return

        pos      = 0  #position within packet
        idPacket = packetByte[pos][0]
        commandText1 = ''
        commandText2 = ''
        commandText3 = ''
        commandText4 = ''
        commandText5 = ''
        commandText6 = ''

        ##############
        ## Servicemode
        if self.serviceMode == True:
            if 112 <= idPacket <= 127:
                if packetByte[pos][0] >> 4 == 0b0111 and len(packetByte) == 3:
                    ##[RCN-214 5] Register/Page Mode packet
                    if (packetByte[pos][0] >> 3) & 1 == 0:
                        output_long  = 'Verify, Register:'
                        output_short = 'v, R:'
                    else:
                        output_long  = 'Write, Register:'
                        output_short = 'w, R:'
                    output_long  += str((packetByte[pos][0] & 0b111) + 1)
                    output_short += str((packetByte[pos][0] & 0b111) + 1)
                    self.put_packetbyte(packetByte, pos, [Ann.DATA,    [output_long, output_short]])
                    pos, error = self.incPos(pos, packetByte)
                    if error == True: return
                    if packetByte[pos-1][0] == 0b01111101 and packetByte[pos][0] == 1:
                        ##[RCN-216 4.2]
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, ['Register/Page Mode (outdated): Page Preset']])
                    else:
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [str(packetByte[pos][0])]])
                    commandText1 = 'Register/Page Mode (outdated)'
                    self.put_packetbytes(packetByte, pos-1, pos, [Ann.COMMAND, [commandText1]])
                    validPacketFound = True
                
                elif packetByte[pos][0] >> 4 == 0b0111 and len(packetByte) == 4:
                    ##[RCN-214 2]
                    commandText1 = 'Service Mode'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, 'Service']])
                    if (packetByte[pos][0] >> 2) & 0b11 == 0b01:
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, ['Verify byte', 'v']])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        cv_addr = (packetByte[pos-1][0] & 0b00000011)*256 + packetByte[pos][0] + 1
                        self.put_packetbyte(packetByte, pos, [Ann.DATA_CV, [str(cv_addr)]])
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['CV']])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['Value']])
                    
                    elif (packetByte[pos][0] >> 2) & 0b11 == 0b11:
                        self.put_packetbyte(packetByte, pos, [Ann.DATA,    ['Write byte', 'w']])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        cv_addr = (packetByte[pos-1][0] & 0b00000011)*256 + packetByte[pos][0] + 1
                        self.put_packetbyte(packetByte, pos, [Ann.DATA_CV, [str(cv_addr)]])
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['CV']])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['Value']])
                        self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                    
                    elif (packetByte[pos][0] >> 2) & 0b11 == 0b10:
                        self.put_packetbyte(packetByte, pos, [Ann.DATA,    ['Bit manipulation', 'bit']])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        cv_addr = (packetByte[pos-1][0] & 0b00000011)*256 + packetByte[pos][0] + 1
                        self.put_packetbyte(packetByte, pos, [Ann.DATA_CV, [str(cv_addr)]])
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['CV']])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        if (packetByte[pos][0] & 0b00010000) == 0b00010000:
                            output_long = 'Write, '
                            output_short = 'w,'
                        else:
                            output_long = 'Verify, '
                            output_short = 'v,'
                        output_long  += str(packetByte[pos][0] & 0b00000111)
                        output_short += str(packetByte[pos][0] & 0b00000111)
                        if (packetByte[pos][0] & 0b00001000) == 0b00001000:
                            output_long  += ', 1'
                            output_short += ',1'
                        else:
                            output_long  += ', 0'
                            output_short += ',0'
                        self.put_packetbyte(packetByte, pos, [Ann.DATA,    [output_long, output_short]])
                        commandText1 = 'Operation, Position, Value'
                        commandText2 = 'Op.,Pos,Value'
                        commandText3 = 'O,P,V'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                    
                    else:
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, ['Reserved for future use', 'Res.']])
                    
                    validPacketFound = True

        #############################
        ## Normal = (Not Servicemode)
        if     (self.serviceMode == False)\
            or (self.serviceMode == True and not (112 <= idPacket <= 127)):
            pos = 0  #position within packet
            if     (0   <= idPacket <= 127)\
                or (192 <= idPacket <= 231):
                ##[RCN-211 3] Multi-Function Decoder
            
                if idPacket == 0:
                    dec_addr = 0
                    self.put_packetbyte(packetByte, pos, [Ann.DATA_DEC, ['Broadcast']])
                    commandText1 = 'Broadcast'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  [commandText1]])
                
                elif 1 <= idPacket <= 127:
                    dec_addr = packetByte[pos][0] & 0b01111111
                    self.put_packetbyte(packetByte, pos, [Ann.DATA_DEC, [str(dec_addr)]])
                    commandText1 = 'Multi Function Decoder with 7 bit address'
                    commandText2 = 'Decoder with 7 bit address'
                    commandText3 = '7 bit addr.'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  [commandText1, commandText2, commandText3]])
                
                elif 192 <= idPacket <= 231:
                    pos, error = self.incPos(pos, packetByte)
                    if error == True: return
                    dec_addr = ((packetByte[pos-1][0] & 0b00111111)*256) + packetByte[pos][0]
                    self.put_packetbytes(packetByte, pos-1, pos, [Ann.DATA_DEC, [str(dec_addr)]])
                    commandText1 = 'Multi Function Decoder with 14 bit address'
                    commandText2 = 'Decoder with 14 bit address'
                    commandText3 = '14 bit addr.'
                    self.put_packetbytes(packetByte, pos-1, pos, [Ann.COMMAND,  [commandText1, commandText2, commandText3]])
            
                pos, error = self.incPos(pos, packetByte)
                if error == True: return
                cmd    = (packetByte[pos][0] & 0b11100000) >> 5
                subcmd = (packetByte[pos][0] & 0b00011111)
                if cmd == 0b000:  
                    ##[RCN-212 2.1] Decoder Control
                    if   subcmd == 0b00000:
                        if dec_addr == 0:
                            ##[RCN-211 4.1]
                            commandText1 = 'Decoder Reset packet'
                            commandText2 = 'Dec. Reset'
                            commandText3 = 'Reset'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  [commandText1, commandText2, commandText3]])
                        else:
                            ##[RCN-212 2.5.1]
                            commandText1 = 'Decoder Reset'
                            commandText2 = 'Dec. Reset'
                            commandText3 = 'Reset'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  [commandText1, commandText2, commandText3]])
                    
                    elif subcmd == 0b00001:
                        ##[RCN-212 2.5.2]
                        commandText1 = 'Decoder Hard Reset'
                        commandText2 = 'Hard Reset'
                        commandText3 = 'Reset'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                    
                    elif subcmd & 0b11110 == 0b00010:
                        ##[RCN-212 2.5.3]
                        commandText1 = 'Factory Test Instruction'
                        commandText2 = 'Fac. Test'
                        commandText3 = 'Test'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                        validPacketFound = True
                    
                    elif subcmd & 0b11110 == 0b01010:
                        ##[RCN-212 2.5.4]
                        self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0] & 0b00000001)]])
                        commandText1 = 'Set Advanced Addressing (CV #29 Bit 5)'
                        commandText2 = 'Set advanced addressing'
                        commandText3 = 'Set adv. addr.'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                    
                    elif subcmd == 0b01111:
                        ##[RCN-212 2.5.5]
                        commandText1 = 'Decoder Acknowledgment Request'
                        commandText2 = 'Dec. Ack Req.'
                        commandText3 = 'Ack Req.'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                    
                    elif subcmd & 0b10000 == 0b10000:
                        ##[RCN-212 2.4.1]
                        commandText1 = 'Consist Control'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1]])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        if subcmd & 0b11110 == 0b10010:
                            if packetByte[pos-1][0] & 1 == 0:
                                value = 'normal'
                            else:
                                value = 'reverse'
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0] & 0b01111111) + ', dir:' + str(value)]])
                            commandText2 = 'Set consist address'
                            commandText3 = 'Set'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2, commandText3]])
                        else:
                            commandText2 = 'Reserved'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                    
                    else:
                        commandText1 = 'Reserved'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1]])
                
                elif cmd == 0b001:  
                    ##[RCN-212 2.1] Advanced Operations Instruction
                    if subcmd == 0b11111:
                        ##[RCN-212 2.2.2]
                        commandText1 = '128 Speed Step Control - Instruction'
                        commandText2 = '128 Speed Step'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2]])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        if dec_addr == 0:
                            output_long  = 'Broadcast'
                            output_short = 'B'
                        else:
                            if packetByte[pos][0] >> 7 == 1:
                                output_long  = 'Forward'
                                output_short = 'F'
                            else:
                                output_long  = 'Reverse'
                                output_short = 'R'
                        if packetByte[pos][0] & 0b01111111 == 0b00000000:
                            output_long  = 'STOP (' + output_long  + ')'
                            output_short = 'STOP (' + output_short + ')'
                        elif packetByte[pos][0] & 0b01111111 == 0b00000001:
                            output_long  = 'EMERGENCY STOP (HALT) (' + output_long  + ')'
                            output_short = 'ESTOP ('                 + output_short + ')'
                        else:
                            speed = str(((packetByte[pos][0]) & 0b01111111)-1)
                            output_long  += ' Speed: ' + speed + ' / 126'
                            output_short += ':'        + speed
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [output_long, output_short]])
                    
                    elif subcmd == 0b11110:
                        ##[RCN-212 2.2.3]
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        commandText1 = 'Special operation mode (unless received via consist address in CV#19)'
                        commandText2 = 'Special operation mode'
                        self.put_packetbytes(packetByte, pos-1, pos, [Ann.COMMAND, [commandText1, commandText2]])
                        output_1 = ''
                        if (packetByte[pos][0] >> 2) & 0b11 == 0b00:
                            output_1 += 'Not part of a multiple traction'
                        elif (packetByte[pos][0] >> 2) & 0b11 == 0b10:
                            output_1 += 'Leading loco of multiple traction'
                        elif (packetByte[pos][0] >> 2) & 0b11 == 0b01:
                            output_1 += 'Middle loco in a multiple traction'
                        elif (packetByte[pos][0] >> 2) & 0b11 == 0b11:
                            output_1 += 'Final loco of a multiple traction'
                        output_1 += ', shunting key:' + str((packetByte[pos][0] >> 4) & 1)
                        output_1 += ', west-bit:'     + str((packetByte[pos][0] >> 5) & 1)
                        output_1 += ', east-bit:'     + str((packetByte[pos][0] >> 6) & 1)
                        output_1 += ', MAN-bit:'      + str((packetByte[pos][0] >> 7) & 1)
                        self.put_packetbytes(packetByte, pos-1, pos, [Ann.DATA,    [output_1]])
                            
                    elif subcmd == 0b11101:
                        ##[RCN-212 2.3.8]
                        commandText1 = 'Analog Function Group'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1]])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        if packetByte[pos][0] == 0b00000001:
                            commandText2 = 'Volume control'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                        elif 0b00010000 <= packetByte[pos][0] <= 0b00011111:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0] & 0b00001111)]])
                            commandText2 = 'Position control'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                        elif 0b10000000 <= packetByte[pos][0] <= 0b11111111:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0] & 0b01111111)]])
                            commandText2 = 'Any control'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                        else:
                            commandText2 = 'Reserved'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['Data']])
                    
                    elif subcmd == 0b11100:
                        ##[RCN-212 2.3.7]
                        commandText1 = 'Speed, Direction, Function'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1]])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        if dec_addr == 0:
                            output_long  = 'Broadcast'
                            output_short = 'B'
                        else:
                            if packetByte[pos][0] >> 7 == 1:
                                output_long  = 'Forward'
                                output_short = 'F'
                            else:
                                output_long  = 'Reverse'
                                output_short = 'R'
                        if packetByte[pos][0] & 0b01111111 == 0b00000000:
                            output_long  = 'STOP (' + output_long  + ')'
                            output_short = 'STOP (' + output_short + ')'
                        elif packetByte[pos][0] & 0b01111111 == 0b00000001:
                            output_long  = 'EMERGENCY STOP (HALT) (' + output_long  + ')'
                            output_short = 'ESTOP ('                 + output_short + ')'
                        else:
                            speed = str(((packetByte[pos][0]) & 0b01111111)-1)    
                            output_long  += ' Speed: ' + speed + ' / 126'
                            output_short += ':'        + speed
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [output_long, output_short]])
                        numbers = [0, 8, 16, 24]
                        for f in numbers:
                            if len(packetByte) > pos+2:  #more data + checksum
                                pos, error = self.incPos(pos, packetByte)
                                if error == True: return
                                value = packetByte[pos][0]
                                output_long  = ''
                                output_short = 'F' + str(f) + ':'
                                for i in range(0, 8):
                                    output_long  += 'F' + str(f + i) + ':' + str(value & 1)
                                    output_short += str(value & 1)
                                    if (i<7):
                                        output_long  += ', '
                                        output_short += ','
                                    value = value >> 1
                                self.put_packetbyte(packetByte, pos, [Ann.DATA, [output_long, output_short]])
                            else:
                                break
                                                    
                    else:
                        commandText1 = 'Reserved'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1]])
                
                elif cmd in [0b010, 0b011]:  
                    ##[RCN-212 2.2.1]
                    if self.speed14 == True:
                        commandText1 = 'Basis Speed and Direction Instruction 14 speed step mode (CV#29=0)'
                        commandText2 = 'Speed + Dir. 14 step'
                        commandText3 = 'Speed 14'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                    else:
                        commandText1 = 'Basis Speed and Direction Instruction 28 speed step mode (CV#29=1)'
                        commandText2 = 'Speed + Dir. 28 step'
                        commandText3 = 'Speed 28'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                    output_long14  = ''
                    output_short14 = ''
                    output_long28  = ''
                    output_short28 = ''
                    bit5           = (subcmd & 0b10000) >> 4
                    if dec_addr == 0:
                        output_long14  = 'Broadcast'
                        output_short14 = 'B'
                    else:
                        if cmd & 0b001 == 0b001:
                            output_long14  = 'Forward'
                            output_short14 = 'F'
                        else:
                            output_long14  = 'Reverse'
                            output_short14 = 'R'
                    output_long28  = output_long14
                    output_short28 = output_short14
                    if subcmd & 0b01111 == 0b00000:
                        output_long14  = 'STOP (' + output_long14  + ')'
                        output_short14 = 'STOP (' + output_short14 + ')'
                        output_long28  = 'STOP (' + output_long28  + ')'
                        output_short28 = 'STOP (' + output_short28 + ')'
                    elif subcmd & 0b01111 == 0b00001:
                        output_long14  = 'EMERGENCY STOP (HALT) (' + output_long14  + ')'
                        output_short14 = 'ESTOP ('                 + output_short14 + ')'
                        output_long28  = 'EMERGENCY STOP (HALT) (' + output_long28  + ')'
                        output_short28 = 'ESTOP ('                 + output_short28 + ')'
                    else:
                        output_long14  += ' Speed: ' + str((subcmd & 0b1111)-1) + ' / 14'
                        output_short14 += ':'       + str((subcmd & 0b1111)-1)
                        output_long28  += ' Speed: ' + str((((((subcmd & 0b01111)-1)*2)-1) + bit5)) + ' / 28'
                        output_short28 += ':'       + str((((((subcmd & 0b01111)-1)*2)-1) + bit5))
                    if dec_addr > 0:
                        output_long14  += ', F0=' + str(bit5)
                        output_short14 += ', F0=' + str(bit5)
                    if self.speed14 == True:
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [output_long14, output_short14]])
                    else:    
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [output_long28, output_short28]])
                
                elif cmd == 0b100:
                    ##[RCN-212 2.3.1]
                    if self.speed14 == True:
                        commandText1 = 'Function Group One Instruction 14 speed step mode (CV#29=0)'
                        commandText2 = 'FG1 14 step'
                        commandText3 = 'FG1'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                    else:    
                        commandText1 = 'Function Group One Instruction 28/128 speed step mode (CV#29=1)'
                        commandText2 = 'FG1 28/128 step'
                        commandText3 = 'FG1'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2, commandText3]])

                    f = 1
                    output_long  = ''
                    output_short = ''
                    value = subcmd
                    for i in range(0, 4):
                        output_long  = output_long  + 'F' + str(f) + ':' + str(value & 1)
                        output_short = output_short + str(value & 1)
                        if i<3:
                            output_long  = output_long  + ', '
                            output_short = output_short + ','
                        value = value >> 1
                        f += 1
                        
                    if self.speed14 == True:
                        output_short = 'F1:' + output_short
                    else:
                        output_long  = 'F0:' + str(subcmd >> 4) + ', ' + output_long
                        output_short = 'F0:' + str(subcmd >> 4) + ','  + output_short
                    self.put_packetbyte(packetByte, pos, [Ann.DATA, [output_long, output_short]])
                
                elif cmd == 0b101:
                    commandText1 = 'Function Group Two Instruction'
                    commandText2 = 'FG2'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2]])
                    if subcmd & 0b10000 == 0b10000:
                        ##[RCN-212 2.3.2]
                        f = 5
                    else:
                        ##[RCN-212 2.3.3]
                        f = 9
                    output_long  = ''
                    output_short = 'F' + str(f) + ':'
                    value = subcmd
                    for i in range(0, 4):
                        output_long  = output_long  + 'F' + str(f) + ':' + str(value & 1)
                        output_short = output_short + str(value & 1)
                        if i<3:
                            output_long  = output_long  + ', '
                            output_short = output_short + ','
                        value = value >> 1
                        f += 1
                    self.put_packetbyte(packetByte, pos, [Ann.DATA, [output_long, output_short]])
                
                elif cmd == 0b110:
                    ##[RCN-212 2.3.4]
                    pos, error = self.incPos(pos, packetByte)
                    if error == True: return
                    commandText1 = 'Future Expansion Instruction'
                    self.put_packetbyte(packetByte, pos-1, [Ann.COMMAND, [commandText1]])
                    if subcmd in [0b11111, 0b11110, 0b11100, 0b11011, 0b11010, 0b11001, 0b11000]: #F13 - F68
                        value = packetByte[pos][0]
                        f = 0
                        if subcmd == 0b11110:
                            f = 13
                        if subcmd == 0b11111:
                            f = 21
                        if subcmd == 0b11000:
                            f = 29
                        if subcmd == 0b11001:
                            f = 37
                        if subcmd == 0b11010:
                            f = 45
                        if subcmd == 0b11011:
                            f = 53
                        if subcmd == 0b11100:
                            f = 61
                        output_long  = ''
                        output_short = 'F' + str(f) + ':'
                        for i in range(0, 8):
                            output_long  = output_long  + 'F' + str(f + i) + ':' + str(value & 1)
                            output_short = output_short + str(value & 1)
                            if i<7:
                                output_long  = output_long  + ', '
                                output_short = output_short + ','
                            value = value >> 1
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [output_long, output_short]])
                        
                    elif subcmd == 0b11101:
                        ##[RCN-212 2.3.5]
                        ##[RCN-217 4.3.1]
                        address = packetByte[pos][0] & 0b01111111
                        commandText1 = 'Binary State Control Instruction short form'
                        commandText2 = 'Binarystate short'
                        self.put_packetbyte(packetByte, pos-1, [Ann.DATA, [commandText1, commandText2]])
                        if address == 0:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0] >> 7)]])
                            commandText3 = 'Broadcast F29-F127'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText3]])
                        elif 1 <= address <= 15:
                            ##[RCN-217 4.3.1]
                            if address == 1:
                                ##[RCN-217 5.3.1]
                                if packetByte[pos][0] >> 7 == 0:
                                    output_long  = 'XF=1 (Requesting the location information)'
                                else:
                                    output_long  = 'XF=1'
                                output_short = 'XF=1'
                            elif address == 2:
                                ##[RCN-217 5.2.2]
                                if packetByte[pos][0] >> 7 == 0:
                                    output_long  = 'XF=2 (Rerail search)'
                                else:
                                    output_long  = 'XF=2'
                                output_short = 'XF=2'
                            else:
                                output_long  = 'XF=' + str(address) + ' (Reserved)'
                                output_short = 'XF=' + str(address) + ' (Res.)'
                            if packetByte[pos][0] >> 7 == 0:
                                output_long  += ':off'
                                output_short += ':off'
                            else:
                                output_long  += ':on'
                                output_short += ':on'
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [output_long, output_short]])
                            commandText3 = 'RailCom'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText3]])
                        elif 16 <= address <= 28:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [hex(packetByte[pos][0]) + '/' + str(packetByte[pos][0])]])
                            commandText3 = 'Special uses'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText3]])
                        else:
                            if packetByte[pos-1][0] >> 7 == 0:
                                output_1 = 'off'
                            else:
                                output_1 = 'on'
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    ['F' + str(address) + ':' + output_1]])
                            
                    elif subcmd == 0b00000:
                        ##[RCN-212 2.3.6]
                        commandText1 = 'Binary State Control Instruction long form'
                        commandText2 = 'Binarystate long'
                        self.put_packetbyte(packetByte, pos-1, [Ann.DATA, ['Binary State Control Instruction long form', 'Binarystate long']])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        address = (packetByte[pos][0]*128) + (packetByte[pos-1][0] & 0b01111111)
                        if packetByte[pos-1][0] >> 7 == 0:
                            output_1 = 'off'
                        else:
                            output_1 = 'on'
                        if address == 0:
                            self.put_packetbytes(packetByte, pos-1, pos, [Ann.DATA,    [output_1]])
                            commandText3 = 'Broadcast F29-F32767'
                            self.put_packetbytes(packetByte, pos-1, pos, [Ann.COMMAND, [commandText3]])
                        elif packetByte[pos-1][0] & 0b01111111 == 0:
                            self.put_packetbytes(packetByte, pos-1, pos, [Ann.ERROR,   ['Use binarystate short', 'Error', 'E']])
                        else:
                            self.put_packetbytes(packetByte, pos-1, pos, [Ann.DATA,    ['F' + str(address) + ':' + output_1]])
                            
                    elif subcmd == 0b00001:
                        ##[RCN-212 2.3.9]
                        if dec_addr != 0:
                            self.put_packetbytes(packetByte, 0, len(packetByte)-2, [Ann.ERROR, ['Only Broadcast allowed', 'Error', 'E']])
                        value = packetByte[pos][0]
                        if (value >> 6) & 0b11 == 0b00:
                            commandText1 = 'Model-Time'
                            self.put_packetbyte(packetByte, pos-1, [Ann.DATA,  ['Model-Time']])
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['00MMMMMM']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['WWWHHHHH']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['U0BBBBBB']])
                            output_long  = self.weekday[packetByte[pos-1][0] >> 5] + ' ' + '{:02.0f}'.format(packetByte[pos-1][0] & 0b00011111) + ':'\
                                           + '{:02.0f}'.format(packetByte[pos-2][0] & 0b00111111) + ' hrs, Update:' + str(packetByte[pos][0] >> 7) + ', Acceleration:' + str(packetByte[pos][0] & 0b00111111)
                            output_short = self.weekday_short[packetByte[pos-1][0] >> 5] + ' ' + '{:02.0f}'.format(packetByte[pos-1][0] & 0b00011111) + ':'\
                                           + '{:02.0f}'.format(packetByte[pos-2][0] & 0b00111111) + ', U:' + str(packetByte[pos][0] >> 7) + ', Acc:' + str(packetByte[pos][0] & 0b00111111)
                        elif (value >> 6) & 0b11 == 0b01:
                            commandText1 = 'Model-Date'
                            self.put_packetbyte(packetByte, pos-1, [Ann.DATA,  ['Model-Date']])
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['010TTTTT']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['MMMMYYYY']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['YYYYYYYY']])
                            output_long  = str(packetByte[pos-2][0] & 0b00011111) + '. ' + self.month[(packetByte[pos-1][0] >> 4)] + str(((packetByte[pos-1][0] & 0b00001111) << 8) + packetByte[pos][0])
                            output_short = str(packetByte[pos-2][0] & 0b00011111) + '.'  + str(packetByte[pos-1][0] >> 4) + '.'    + str(((packetByte[pos-1][0] & 0b00001111) << 8) + packetByte[pos][0])
                        else:
                            output_long  = 'Reserved'
                            output_short = 'Res.'
                            self.put_packetbyte(packetByte, pos-1, [Ann.DATA,   ['Reserved']])
                        self.put_packetbytes(packetByte, pos-2, pos, [Ann.DATA, [output_long, output_short]])
                            
                    elif subcmd == 0b00010:
                        ##[RCN-212 2.3.10]
                        if dec_addr != 0:
                            self.put_packetbytes(packetByte, 0, len(packetByte)-2, [Ann.ERROR, ['Only Broadcast allowed', 'Error', 'E']])
                        if len(packetByte) == 5 or len(packetByte) == 6:
                            commandText1 = 'Systemtime'
                            self.put_packetbyte(packetByte, pos-1,   [Ann.DATA,    ['Systemtime']])
                        if len(packetByte) == 7 or len(packetByte) == 8:
                            commandText1 = 'Systemtime (deprecated)'
                            self.put_packetbyte(packetByte, pos-1,   [Ann.DATA,    ['Systemtime (deprecated)']])
                        self.put_packetbyte(packetByte, pos,         [Ann.COMMAND, ['MMMMMMMM']])
                        value = packetByte[pos][0]
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        self.put_packetbyte(packetByte, pos,         [Ann.COMMAND, ['MMMMMMMM']])
                        value = value * 256 + packetByte[pos][0]
                        if len(packetByte) == 5 or len(packetByte) == 6:
                            self.put_packetbytes(packetByte, pos-1, pos, [Ann.DATA, [str(value) + ' ms since systemstart (' + '{:.0f}'.format(value/1000) + ' seconds)',\
                                                                                     str(value) + ' ms since systemstart', str(value)]])
                        if len(packetByte) == 7 or len(packetByte) == 8:
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos,         [Ann.COMMAND, ['MMMMMMMM']])
                            value = value * 256 + packetByte[pos][0]
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos,         [Ann.COMMAND, ['MMMMMMMM']])
                            value = value * 256 + packetByte[pos][0]
                            self.put_packetbytes(packetByte, pos-3, pos, [Ann.DATA, [str(value) + ' ms since systemstart (' + '{:.0f}'.format(value/60000) + ' minutes = ' + '{:.1f}'.format(value/3600000) + ' hours)',\
                                                                                     str(value) + ' ms since systemstart', str(value)]])
                    else:
                        commandText1 = 'Reserved'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1]])
                
                elif cmd == 0b111:  
                    if subcmd & 0b10000 == 0b10000:  #Short Form
                        ##[RCN-214 3]
                        ##[RCN-217 4.3.2]
                        commandText1 = 'Configuration Variable Access Instruction - Short Form'
                        commandText2 = 'CV Access Instruction short'
                        commandText3 = 'CV short'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND,     [commandText1, commandText2, commandText3]])
                        if subcmd & 0b1111 == 0b0000:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    ['Not available for use', 'Not av.']])
                        elif subcmd & 0b1111 == 0b0010:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    ['Acceleration Value (CV#23)', 'CV#23']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['Data']])
                        elif subcmd & 0b1111 == 0b0011:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    ['Deceleration Value (CV#24)', 'CV#24']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['Data']])
                        elif subcmd & 0b1111 == 0b0100:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    ['Write CV#17 + CV#18', 'w CV#17+18']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['CV17']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['CV18']])
                        elif subcmd & 0b1111 == 0b0101:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    ['Write CV#31 + CV#32', 'w CV#31+32']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['CV31']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['CV32']])
                        elif subcmd & 0b1111 == 0b1001:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    ['Reserved (outdated: Service Mode Decoder Lock Instruction)', 'Res. (old: Dec. Lock)', 'Res.']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str((packetByte[pos][0] & 0b01111111))]])
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['Short address', 'Addr.']])
                        else:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    ['Reserved (maybe service mode packet)', 'Reserved', 'Res.']])
                            
                    elif    (pos == 1 and len(packetByte) == 5)\
                         or (pos == 2 and len(packetByte) == 6):
                        ##[RCN-214 2]
                        ##[RCN-217 5.1]
                        commandText1 = 'Configuration Variable Access Instruction - Long Form (POM)'
                        commandText2 = 'CV Access Instruction long (POM)'
                        commandText3 = 'CV long (POM)'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                        if (subcmd >> 2) & 0b11 in [0b01, 0b11, 0b10]:
                            if (subcmd >> 2) & 0b11 == 0b01:
                                output_long  = 'Read/Verify byte'
                                output_short = 'r/v'
                            elif (subcmd >> 2) & 0b11 == 0b11:
                                output_long  = 'Write byte'
                                output_short = 'w'
                            else:    
                                output_long  = 'Bit manipulation'
                                output_short = 'Bit'
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,       [output_long, output_short]])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            cv_addr = (packetByte[pos-1][0] & 0b00000011)*256 + packetByte[pos][0] + 1
                            self.put_packetbyte(packetByte, pos, [Ann.DATA_CV,    [str(cv_addr)]])
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND,    ['CV']])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            if (subcmd >> 2) & 0b11 != 0b10:
                                self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                                self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['Value']])
                            else:    
                                if packetByte[pos][0] & 0b10000 == 0b10000:
                                    output_long  = 'Write, '
                                    output_short = 'w,'
                                else:
                                    output_long  = 'Verify, '
                                    output_short = 'v,'
                                output_long  += str(packetByte[pos][0] & 0b00000111)
                                output_short += str(packetByte[pos][0] & 0b00000111)
                                if packetByte[pos][0] & 0b1000 == 0b1000:
                                    output_long  = output_long  + ', 1'
                                    output_short = output_short + ',1'
                                else:
                                    output_long  = output_long  + ', 0'
                                    output_short = output_short + ',0'
                                self.put_packetbyte(packetByte, pos, [Ann.DATA,    [output_long, output_short]])
                                commandText4 = 'Operation, Position, Value'
                                commandText5 = 'Op.,Pos,Value'
                                commandText6 = 'O,P,V'
                                self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText4, commandText5, commandText6]])
                        else:
                            output_long  = 'Reserved for future use'
                            output_short = 'Res.'
                            self.put_packetbyte(packetByte, pos, [Ann.DATA, [output_long, output_short]])
                            
                    elif    (pos == 1 and len(packetByte) >= 6)\
                         or (pos == 2 and len(packetByte) >= 7):
                        ##[RCN-214 4]
                        ##[RCN-217 5.5]
                        commandText1 = 'XPOM'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1]])
                        if (subcmd >> 2) & 0b11 in [0b01, 0b11, 0b10]:
                            if (subcmd >> 2) & 0b11 == 0b01:
                                output_long  = 'Read bytes'
                                output_short = 'r'
                            elif (subcmd >> 2) & 0b11 == 0b11:
                                output_long  = 'Write byte(s)'
                                output_short = 'w'
                            elif (subcmd >> 2) & 0b11 == 0b10:
                                output_long  = 'Bit write'
                                output_short = 'bit'
                            output_long  += ', SS:' + str(packetByte[pos][0] & 0b11)
                            output_short += ',SS:'  + str(packetByte[pos][0] & 0b11)
                            self.put_packetbyte(packetByte, pos,         [Ann.DATA,    [output_long, output_short]])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            cv_addr = (packetByte[pos-2][0]*256 + packetByte[pos-1][0])*256 + packetByte[pos][0] + 1
                            self.put_packetbytes(packetByte, pos-2, pos, [Ann.DATA_CV, [str(cv_addr)]])
                            self.put_packetbytes(packetByte, pos-2, pos, [Ann.COMMAND, ['CV']])
                            if (subcmd >> 2) & 0b11 == 0b01:  ##read command end
                                pass
                            else:
                                ##[RCN-217 6.7]
                                pos, error = self.incPos(pos, packetByte)
                                if error == True: return
                                if      (subcmd >> 2) & 0b11    == 0b10\
                                    and packetByte[pos][0] >> 4 == 0b1111:  ##Bit write
                                    output_long  = str(packetByte[pos][0] & 0b00000111)
                                    output_short = str(packetByte[pos][0] & 0b00000111)
                                    if packetByte[pos][0] & 0b1000 == 0b1000:
                                        output_long  += ', 1'
                                        output_short += ',1'
                                    else:
                                        output_long  += ', 0'
                                        output_short += ',0'
                                    self.put_packetbyte(packetByte, pos, [Ann.DATA,        [output_long, output_short]])
                                    commandText4 = 'Position, Value'
                                    commandText5 = 'Pos, Value'
                                    commandText6 = 'P,V'
                                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText4, commandText5, commandText6]])
                                elif (subcmd >> 2) & 0b11 == 0b11:
                                    commandText4 = 'Data'
                                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND,     [commandText4 + '-1']])
                                    self.put_packetbyte(packetByte, pos, [Ann.DATA,        [str(packetByte[pos][0])]])
                                    if len(packetByte) > pos+2: #more data + checksum
                                        pos, error = self.incPos(pos, packetByte)
                                        if error == True: return
                                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText4 + '-2']])
                                        self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                                    if len(packetByte) > pos+2: #more data + checksum
                                        pos, error = self.incPos(pos, packetByte)
                                        if error == True: return
                                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText4 + '-3']])
                                        self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                                    if len(packetByte) > pos+2: #more data + checksum
                                        pos, error = self.incPos(pos, packetByte)
                                        if error == True: return
                                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText4 + '-4']])
                                        self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                        else:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA, ['Reserved for future use', 'Res.']])
                                    
            elif 128 <= idPacket <= 191:
                ##[RCN-211 3] Accessory Decoder
                pos, error = self.incPos(pos, packetByte)
                if error == True: return
                
                #10AAAAAA 1AAADAAR                             #Basic Accessory Decoder Packet Format
                #10111111 1000DAAR                             #Broadcast Command for Basic Accessory Decoders (only NMRA, not RCN)
                #                                              #D:activate/deactivate addressed device AA:Pair of 4 R:Pair of output
                #10111111 10000110                             #ESTOP
                #10AAAAAA 1AAA1AA0 1110CCVV VVVVVVVV DDDDDDDD  #Basic Accessory Decoder Packet address for operations mode programming (POM)
                #10AAAAAA 0AAA0AA1 DDDDDDDD                    #Extended Accessory Decoder Control Packet Format
                #10111111 00000111 DDDDDDDD                    #Broadcast Command for Extended Accessory Decoders 
                #10111111 00000111 00000000                    #ESTOP
                #10AAAAAA 0AAA0AA1 1110CCVV VVVVVVVV DDDDDDDD  #Extended Decoder Control Packet address for operations mode programming (POM)
                #10AAAAAA 0AAA1AAT                             #NOP
                #  ^^^^^^  ^^^ ^^
                #  A1      A2  A3

                A1       = packetByte[pos-1][0]        & 0b00111111        #6 bits addr. high
                A2       = ~((packetByte[pos][0] >> 4) & 0b0111) & 0b0111  #3 bits addr. low (inverted)
                A3       = (packetByte[pos][0]         & 0b00000110) >> 1  #2 bits bits 1-2 of bit two (port address)        
                decoder  = (A2 << 6) + A1        
                port     =  A3        
                decaddr  = (A2 << 8) + (A1 << 2) + A3 - 3 
                acc_addr = decaddr + self.AddrOffset
                if decaddr < 1:
                    self.put_packetbytes(packetByte, pos-1, pos, [Ann.ERROR, ['Address < 1 not allowed', 'Error', 'E']])
                
                pom = False
                if packetByte[pos][0] & 0b10001000 == 0b00001000:
                    ##[RCN-213 2.5]
                    ##[RCN-217 4.3.3]
                    commandText1 = 'Railcom NOP (AccQuery)'
                    commandText2 = 'RC NOP'
                    self.put_packetbyte(packetByte, pos,   [Ann.DATA, ['Railcom NOP (AccQuery)', 'RC NOP']])
                    self.put_packetbyte(packetByte, pos-1, [Ann.DATA_ACC, [str(acc_addr)]])
                    if packetByte[pos][0] & 1 == 0:
                        commandText4 = 'Basic Accessory Decoder'
                        commandText5 = 'Basic Accessory'
                        commandText6 = 'Basic Acc.'
                        self.put_packetbyte(packetByte, pos-1, [Ann.COMMAND, [commandText4, commandText5, commandText6]])
                    else:
                        commandText4 = 'Extended Accessory Decoder'
                        commandText5 = 'Ext. Acc.'
                        self.put_packetbyte(packetByte, pos-1, [Ann.COMMAND, [commandText4, commandText5]])
                
                elif packetByte[pos][0] & 0b10000000 == 0b10000000:
                    if     len(packetByte) == 3\
                        or len(packetByte) == 4:
                        ##[RCN-213 2.1]
                        commandText1 = 'Basic Accessory Decoder'
                        commandText2 = 'Basic Accessory'
                        commandText3 = 'Basic Acc.'
                        self.put_packetbyte(packetByte, pos-1, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                        if acc_addr+3 == 2047:
                            ##[RCN-213 2.2]
                            if (packetByte[pos][0] >> 3) & 1 == 0 and packetByte[pos][0] & 1 == 0:
                                self.put_packetbyte(packetByte, pos-1, [Ann.DATA_ACC, ['Broadcast']])
                                commandText4 = 'Broadcast'
                                commandText5 = 'ESTOP'
                                self.put_packetbyte(packetByte, pos-1, [Ann.COMMAND,  [commandText4]])
                                self.put_packetbyte(packetByte, pos,   [Ann.DATA,     [commandText5]])
                            else:
                                self.put_packetbyte(packetByte, pos,   [Ann.INFO,    ['Unknown (maybe NMRA-Broadcast)', 'Unknown']])
                        else:
                            if len(packetByte) == 3:
                                output_1 = str(packetByte[pos][0] & 1)
                                if (packetByte[pos][0] >> 3) & 1 == 0:
                                    output_2 = 'off'
                                else:
                                    output_2 = 'on'
                                self.put_packetbyte(packetByte, pos-1,       [Ann.DATA_ACC, [str(acc_addr) + ' (decoder:' + str(decoder) + ', port:' + str(port) + ')',\
                                                                                             str(acc_addr) + ' (' + str(decoder) + ',' + str(port) + ')', str(acc_addr)]])
                                self.put_packetbyte(packetByte, pos,         [Ann.DATA,     [str(output_1) + ':' + str(output_2)]])
                            elif    len(packetByte) == 4\
                                and packetByte[pos][0] & 0b1001 == 0b0000:
                                pos, error = self.incPos(pos, packetByte)
                                if error == True: return
                                if packetByte[pos][0] == 0: 
                                    self.put_packetbyte(packetByte, pos-1,       [Ann.DATA_ACC, [str(acc_addr) + ' (decoder:' + str(decoder) + ', port:' + str(port) + ')',\
                                                                                                 str(acc_addr) + ' (' + str(decoder) + ',' + str(port) + ')', str(acc_addr)]])
                                    commandText4 = 'Decoder reset'
                                    commandText5 = 'Reset'
                                    self.put_packetbyte(packetByte, pos,         [Ann.COMMAND,  [commandText4, commandText5]])
                                else:
                                    self.put_packetbytes(packetByte, pos-1, pos, [Ann.INFO, ['Unknown']])
                            else:        
                                self.put_packetbyte(packetByte, pos, [Ann.INFO, ['Unknown']])
                    
                    elif len(packetByte) == 6:
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        if packetByte[pos][0] >> 4 == 0b1110:
                            ##[RCN-217 6.2]
                            pom = True
                            commandText1 = 'POM for Basic Accessory Decoder'
                            commandText2 = 'POM Basic Accessory'
                            commandText3 = 'POM Basic Acc.'
                            self.put_packetbyte(packetByte, pos-2,           [Ann.COMMAND,  [commandText1, commandText2, commandText3]])
                            self.put_packetbyte(packetByte, pos-1,           [Ann.DATA_ACC, [str(acc_addr) + ' (decoder:' + str(decoder) + ', port:' + str(port) + ')',\
                                                                                             str(acc_addr) + ' (' + str(decoder) + ',' + str(port) + ')', str(acc_addr)]])
                            self.put_packetbyte(packetByte, pos-1,           [Ann.COMMAND,  ['Address', 'Addr.']])
                        else:
                            self.put_packetbytes(packetByte, pos-2, pos,     [Ann.INFO, ['Unknown']])
                
                else:
                    ##[RCN-213 2.3]
                    if len(packetByte) == 4:
                        commandText1 = 'Extended Accessory Decoder Control Packet'
                        commandText2 = 'Extended Accessory'
                        commandText3 = 'Ext. Acc.'
                        self.put_packetbyte(packetByte, pos-1, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        if acc_addr+3 == 2047:
                            ##[RCN-213 2.4]
                            if packetByte[pos][0] == 0:
                                self.put_packetbyte(packetByte, pos-1,       [Ann.DATA_ACC, ['Broadcast']])
                                commandText4 = 'Broadcast'
                                commandText5 = 'ESTOP'
                                self.put_packetbyte(packetByte, pos-1,       [Ann.COMMAND,  [commandText4]])
                                self.put_packetbyte(packetByte, pos,         [Ann.DATA,     [commandText5]])
                            else:                                            
                                self.put_packetbyte(packetByte, pos-1,       [Ann.DATA,  [hex(packetByte[pos-1][0]) + '/' + str(packetByte[pos-1][0])]])
                                self.put_packetbyte(packetByte, pos,         [Ann.DATA,  [hex(packetByte[pos][0]) + '/' + str(packetByte[pos][0])]])
                                self.put_packetbytes(packetByte, pos-1, pos, [Ann.INFO, ['Unknown']])
                        else:                                                
                            self.put_packetbytes(packetByte, pos-2, pos-1,   [Ann.DATA_ACC, [str(acc_addr) + ' (decoder:' + str(decoder) + ', port:' + str(port) + ')',\
                                                                                             str(acc_addr) + ' (' + str(decoder) + ',' + str(port) + ')', str(acc_addr)]])
                            self.put_packetbyte(packetByte, pos,             [Ann.DATA, ['Aspect:' + hex(packetByte[pos][0]) + '/' + str(packetByte[pos][0])]])
                            if packetByte[pos][0] & 0b01111111 == 0b01111111:
                                output_1 = 'on'
                            elif packetByte[pos][0] & 0b01111111 == 0b00000000:
                                output_1 = 'off'
                            else:
                                output_1 = str(packetByte[pos][0] & 0b01111111)
                            self.put_packetbyte(packetByte, pos,             [Ann.COMMAND, ['Switching time:' + output_1 + ', output:' + str((packetByte[pos][0] >> 7))]])
                    
                    elif len(packetByte) == 6:
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        if packetByte[pos][0] >> 4 == 0b1110:
                            ##[RCN-217 6.2]
                            pom = True
                            commandText1 = 'POM for Extended Accessory Decoder'
                            commandText2 = 'POM Extended Accessory'
                            commandText3 = 'POM Extended Acc.'
                            self.put_packetbyte(packetByte, pos-2,           [Ann.COMMAND,  [commandText1, commandText2, commandText3]])
                            self.put_packetbyte(packetByte, pos-1,           [Ann.DATA_ACC, [str(acc_addr) + ' (decoder:' + str(decoder) + ', port:' + str(port) + ')',\
                                                                                             str(acc_addr) + ' (' + str(decoder) + ',' + str(port) + ')', str(acc_addr)]])
                            self.put_packetbyte(packetByte, pos-1,           [Ann.COMMAND,  ['Address', 'Addr.']])
                        else:
                            self.put_packetbytes(packetByte, pos-2, pos,     [Ann.INFO, ['Unknown']])
                
                if pom == True:
                    subcmd = (packetByte[pos][0] & 0b00011111)
                    if (subcmd >> 2) & 0b11 in [0b01, 0b11, 0b10]:
                        if (subcmd >> 2) & 0b11 == 0b01:
                            output_long  = 'Read/Verify byte'
                            output_short = 'r/v'
                        elif (subcmd >> 2) & 0b11 == 0b11:
                            output_long  = 'Write byte'
                            output_short = 'w'
                        else:    
                            output_long  = 'Bit manipulation'
                            output_short = 'Bit'
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [output_long, output_short]])
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['Mode']])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        cv_addr = (packetByte[pos-1][0] & 0b00000011)*256 + packetByte[pos][0] + 1
                        self.put_packetbyte(packetByte, pos, [Ann.DATA_CV, [str(cv_addr)]])
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['CV']])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        if (subcmd >> 2) & 0b11 != 0b10:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [str(packetByte[pos][0])]])
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, ['Value']])
                        else:    
                            if packetByte[pos][0] & 0b10000 == 0b10000:
                                output_long  = 'Write, '
                                output_short = 'w,'
                            else:
                                output_long  = 'Verify, '
                                output_short = 'v,'
                            output_long  += str(packetByte[pos][0] & 0b00000111)
                            output_short += str(packetByte[pos][0] & 0b00000111)
                            if packetByte[pos][0] & 0b1000 == 0b1000:
                                output_long  = output_long  + ', 1'
                                output_short = output_short + ',1'
                            else:
                                output_long  = output_long  + ', 0'
                                output_short = output_short + ',0'
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,    [output_long, output_short]])
                            commandText4 = 'Operation, Position, Value'
                            commandText5 = 'Op.,Pos,Value'
                            commandText6 = 'O,P,V'
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText4, commandText5, commandText6]])
                    else:
                        output_long  = 'Reserved for future use'
                        output_short = 'Res.'
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [output_long, output_short]])
                
            elif 232 <= idPacket <= 252:
                ##[RCN-211 3] Reserved
                commandText1 = 'Reserved'
                self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1]])
            
            elif idPacket == 253:
                ##[s-9.2.1.1]
                commandText1 = 'Advanced Extended Packet'
                commandText2 = 'Adv. Ext. Packet'
                commandText3 = 'Adv. Ext.'
                self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1, commandText2, commandText3]])
                if len(packetByte) <= 6:
                    for i in range (pos, len(packetByte)-1 -1):
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        output_1  = '?:' + hex(packetByte[pos][0]) + '/' + str(packetByte[pos][0])
                        self.put_packetbyte(packetByte, pos,         [Ann.DATA,    [output_1]])
                        commandText4 = 'S-9.1.1 in definition phase'
                        self.put_packetbytes(packetByte, 1, pos,     [Ann.COMMAND, [commandText4]])
                else:
                    for i in range (pos, len(packetByte)-2 -1):
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        output_1  = '?:' + hex(packetByte[pos][0]) + '/' + str(packetByte[pos][0])
                        self.put_packetbyte(packetByte, pos,         [Ann.DATA,    [output_1]])
                    pos, error = self.processCRC(pos, packetByte)
                    if error == True: return
                    commandText4 = 'S-9.1.1 in definition phase'
                    self.put_packetbytes(packetByte, 1, pos-1  ,     [Ann.COMMAND, [commandText4]])
                
            elif idPacket == 254:
                ##[RCN-218]
                commandText1 = 'DCC-A'
                self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText1]])
                pos, error = self.incPos(pos, packetByte)
                if error == True: return
                commandByte = packetByte[pos][0]
                if commandByte == 0b00000000:
                    commandText2 = 'GET_DATA_START'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                elif commandByte == 0b00000001:
                    commandText2 = 'GET_DATA_CONT'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                elif commandByte == 0b00000010:
                    commandText2 = 'SET_DATA_START'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                    self.put_packetbyte(packetByte, pos, [Ann.INFO,    ['currently not defined']])
                elif commandByte == 0b00000011:
                    commandText2 = 'SET_DATA_CONT'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                    self.put_packetbyte(packetByte, pos, [Ann.INFO,    ['currently not defined']])
                elif 0b00000100 <= commandByte <= 0b00001111:
                    commandText2 = 'Reserved'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                elif 0b00010000 <= commandByte <= 0b10111111:
                    commandText2 = 'Reserved'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                elif 0b11000000 <= commandByte <= 0b11001111:
                    commandText2 = 'Reserved'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText2]])
                elif 0b11010000 <= commandByte <= 0b11011111:
                    commandText2 = 'Reserved'
                    self.putx(packetByte[pos][1][0], packetByte[pos][1][4],   [Ann.COMMAND, [commandText2]])
                    pos, error = self.incPos(pos, packetByte)
                    if error == True: return
                    HHHH = (commandByte & 0b00001111 << 8) + packetByte[pos][0]
                    self.putx(packetByte[pos-1][1][4], packetByte[pos][1][8], [Ann.COMMAND, ['12 bit manufacturer ID', 'manufacturer ID']])
                    self.putx(packetByte[pos-1][1][4], packetByte[pos][1][8], [Ann.DATA,    [hex(HHHH)]])
                    UUUU = 0
                    for i in range (1, 5):
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        UUUU = (UUUU << 8) + packetByte[pos][0]
                    self.put_packetbytes(packetByte, pos-3, pos, [Ann.DATA,     [hex(UUUU)]])
                    self.put_packetbytes(packetByte, pos-3, pos, [Ann.COMMAND,  ['32 bit decoder ID', 'decoder ID']])
                    pos, error = self.incPos(pos, packetByte)
                    if error == True: return
                    commandText4 = 'Subcommand'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  [commandText4]])
                    BBBB = packetByte[pos][0]
                    output_short = str(BBBB)
                    errorPacket = False
                    if BBBB == 0b11111111:
                        commandText5 = 'Read ShortInfo'
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [commandText5]])
                    elif BBBB == 0b11111110:
                        commandText5 = 'Read Block'
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [commandText5]])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        commandText6 = 'Data space number'
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  [commandText6, 'Data space', 'Space']])
                        output_short = str(packetByte[pos][0])
                        self.put_packetbyte(packetByte, pos, [Ann.DATA,     [output_short]])
                        if len(packetByte) == 15:
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  ['CV31']])
                            output_short = str(packetByte[pos][0])
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,     [output_short]])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  ['CV32']])
                            output_short = str(packetByte[pos][0])
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,     [output_short]])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  ['CV address']])
                            output_short = str(packetByte[pos][0])
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,     [output_short]])
                            pos, error = self.incPos(pos, packetByte)
                            if error == True: return
                            self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  ['Number of CVs requested', '#CVs']])
                            output_short = str(packetByte[pos][0])
                            self.put_packetbyte(packetByte, pos, [Ann.DATA,     [output_short]])
                        elif len(packetByte) != 11:
                            self.put_packetbytes(packetByte, 0, len(packetByte)-1, [Ann.ERROR, ['Unknown Paket, length: ' + str(len(packetByte)), 'Error', 'E']])
                            errorPacket = True
                    elif BBBB == 0b11111101:
                        commandText5 = 'Reserved (Read Background)'
                        commandText6 = 'Reserved'
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [commandText5, commandText6]])
                    elif BBBB == 0b11111100:
                        commandText5 = 'Reserved (Write Block)'
                        commandText6 = 'Reserved'
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [commandText5, commandText6]])
                    elif BBBB == 0b11111011:
                        commandText5 = 'Set decoder internal state'
                        commandText6 = 'Set state'
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, [commandText5, commandText6]])
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  ['State']])
                        NNNN = packetByte[pos][0]
                        if NNNN == 0b11111111:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA, ['delete changeflags']])
                        else:
                            self.put_packetbyte(packetByte, pos, [Ann.DATA, ['Reserved']])
                    else:
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, ['Reserved']])
                    if errorPacket == False:
                        pos, error = self.processCRC(pos, packetByte)
                        if error == True: return
                elif 0b11100000 <= commandByte <= 0b11101111:
                    commandText2 = 'LOGON_ASSIGN'
                    self.putx(packetByte[pos][1][0], packetByte[pos][1][4],   [Ann.COMMAND, [commandText2]])
                    pos, error = self.incPos(pos, packetByte)
                    if error == True: return
                    HHHH = (commandByte & 0b00001111 << 8) + packetByte[pos][0]
                    self.putx(packetByte[pos-1][1][4], packetByte[pos][1][8], [Ann.COMMAND, ['12 bit manufacturer ID', 'manufacturer ID']])
                    self.putx(packetByte[pos-1][1][4], packetByte[pos][1][8], [Ann.DATA,    [hex(HHHH)]])
                    UUUU = 0
                    for i in range (1, 5):
                        pos, error = self.incPos(pos, packetByte)
                        if error == True: return
                        UUUU = (UUUU << 8) + packetByte[pos][0]
                    self.put_packetbytes(packetByte, pos-3, pos, [Ann.DATA,     [hex(UUUU)]])
                    self.put_packetbytes(packetByte, pos-3, pos, [Ann.COMMAND,  ['32 bit decoder ID', 'decoder ID']])
                    pos, error = self.incPos(pos, packetByte)
                    if error == True: return
                    pos, error = self.incPos(pos, packetByte)
                    if error == True: return
                    if ((packetByte[pos-1][0] & 0b11000000) >> 6) == 0b11:
                        self.putx(packetByte[pos-1][1][0], packetByte[pos-1][1][2], [Ann.COMMAND,  ['Reserved', 'Res']])
                        self.putx(packetByte[pos-1][1][2], packetByte[pos][1][8],   [Ann.COMMAND,  ['decoder address']])
                        output_short = hex(((packetByte[pos-1][0] & 0b00111111) <<8 ) + packetByte[pos][0])
                        self.putx(packetByte[pos-1][1][2], packetByte[pos][1][8],   [Ann.DATA,     [output_short]])
                    else:
                        self.put_packetbytes(packetByte, pos-1, pos,                [Ann.INFO,     ['ignore command']])
                    output_short = '{0:b}'.format((packetByte[pos-1][0] & 0b11000000) >> 6)
                    self.putx(packetByte[pos-1][1][0], packetByte[pos-1][1][2],     [Ann.DATA,     [output_short]])
                    pos, error = self.processCRC(pos, packetByte)
                    if error == True: return
                if commandByte == 0b11110000:
                    commandText4 = 'Reserved'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText4]])
                elif 0b11110001 <= commandByte <= 0b11111011:
                    commandText4 = 'Reserved'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND, [commandText4]])
                elif 0b11111100 <= commandByte <= 0b11111111:
                    commandText4 = 'LOGON_ENABLE'
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  [commandText4]])
                    GG = commandByte & 0b00000011
                    if GG == 0b00:
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, ['ALL: all decoders resond', 'ALL']])
                    elif GG == 0b01:
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, ['LOCO: mobile decoders only', 'LOCO']])
                    elif GG == 0b10:
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, ['ACC: accessory decoders only', 'ACC']])
                    elif GG == 0b11:
                        self.put_packetbyte(packetByte, pos, [Ann.DATA, ['NOW: all decoders (regardless of backoff)', 'NOW']])
                    pos, error = self.incPos(pos, packetByte)
                    if error == True: return
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  ['CID MSB', 'CID']])
                    output_short = hex(packetByte[pos][0])
                    self.put_packetbyte(packetByte, pos, [Ann.DATA,     [output_short]])
                    pos, error = self.incPos(pos, packetByte)
                    if error == True: return
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  ['CID LSB', 'CID']])
                    output_short = hex(packetByte[pos][0])
                    self.put_packetbyte(packetByte, pos, [Ann.DATA,     [output_short]])
                    pos, error = self.incPos(pos, packetByte)
                    if error == True: return
                    self.put_packetbyte(packetByte, pos, [Ann.COMMAND,  ['SessionID']])
                    output_short = str(packetByte[pos][0])
                    self.put_packetbyte(packetByte, pos, [Ann.DATA,     [output_short]])
            
            elif idPacket == 255:
                ##[RCN-211 3] Idle
                pos, error = self.incPos(pos, packetByte)
                if error == True: return
                if packetByte[pos][0] == 0:
                      ##[RCN-211 4.2] Idle
                    commandText1 = 'Idle'
                    self.put_packetbytes(packetByte, pos-1, pos, [Ann.COMMAND, [commandText1]])
                else: ##[RCN-211 4.3] System command
                    validPacketFound = True
                    commandText1 = 'RailComPlus®'
                    self.put_packetbytes(packetByte, pos-1, pos-1, [Ann.COMMAND, [commandText1]])
                    if len(packetByte) >= 5 and packetByte[pos+1][0] == 62 and packetByte[pos+2][0] == 7 and packetByte[pos+3][0] == 64:
                        commandText4 = 'System command (not documented) (IDNotify?)'
                        commandText5 = 'System command'
                        self.put_packetbytes(packetByte, pos, len(packetByte)-2, [Ann.COMMAND, [commandText4, commandText5]])
                    else:
                        commandText4 = 'System command (not documented)'
                        commandText5 = 'System command'
                        self.put_packetbytes(packetByte, pos, len(packetByte)-2, [Ann.COMMAND, [commandText4, commandText5]])
                    pos -= 1 ##

        ## remaining bytes in packet
        for x in range(pos+1, len(packetByte) -1):
            output_1  = '?:' + hex(packetByte[x][0]) + '/' + str(packetByte[x][0])
            self.put_packetbyte(packetByte, x,         [Ann.DATA, [output_1]])
            if validPacketFound == False:
                self.put_packetbyte(packetByte, x,     [Ann.COMMAND, [output_1]])
                if self.serviceMode == False and 112 <= idPacket <= 127:
                    self.put_packetbyte(packetByte, x, [Ann.INFO, ['Unknown (maybe service mode packet)', 'Unknown']])
                elif self.serviceMode == True:
                    self.put_packetbyte(packetByte, x, [Ann.INFO, ['Unknown (maybe operation mode packet)', 'Unknown']])
                else:
                    self.put_packetbyte(packetByte, x, [Ann.INFO, ['Unknown']])


        ##################
        ##[RCN-211 2] Checksum
        if pos+1 < len(packetByte):
            output_1 = ''
            checksum = packetByte[0][0]
            for x in range(1, len(packetByte) -1):
                checksum = checksum ^ packetByte[x][0]
            if checksum == packetByte[len(packetByte)-1][0]:
                output_1 = 'OK'
                self.put_packetbyte(packetByte, len(packetByte)-1,     [Ann.FRAME, ['Checksum: ' + output_1, output_1]])
            else:
                output_1 = hex(checksum) + '<>' + hex(packetByte[len(packetByte)-1][0])
                self.put_packetbytes(packetByte, 0, len(packetByte)-1, [Ann.ERROR, ['Checksum', 'Error', 'E']])
                self.put_packetbyte(packetByte, len(packetByte)-1,     [Ann.FRAME_OTHER, ['Checksum: ' + output_1, output_1]])
        else:
            self.put_packetbytes(packetByte, 0, len(packetByte)-1,     [Ann.ERROR, ['Checksum missing', 'Error', 'E']])

        
        ###################
        ## Search functions
        ## byte
        byte_found = False
        for x in range(0, len(packetByte)):
            if self.byte_search == packetByte[x][0]:
                byte_found = True
                if (  (self.dec_addr_search < 0 and self.acc_addr_search < 0 and self.cv_addr_search < 0)
                    or dec_addr == self.dec_addr_search
                    or acc_addr == self.acc_addr_search
                    or cv_addr  == self.cv_addr_search
                    ): 
                    self.put_packetbyte(packetByte, x, [Ann.SEARCH_BYTE, ['BYTE:' + hex(self.byte_search) + '/' + str(self.byte_search)]])
        ## dec_addr
        if  (   self.dec_addr_search == dec_addr
            and (   self.byte_search < 0
                 or byte_found       == True)
            ):
            self.put_packetbytes(packetByte, 0, len(packetByte)-2, [Ann.SEARCH_DEC, ['DECODER:' + str(self.dec_addr_search)]])
        ## acc_addr
        if  (   self.acc_addr_search == acc_addr
            and (   self.byte_search < 0
                 or byte_found       == True)
            ):
            self.put_packetbytes(packetByte, 0, len(packetByte)-2, [Ann.SEARCH_ACC, ['ACCESSORY:' + str(self.acc_addr_search)]])
        ## cv_addr
        if  (    self.cv_addr_search == cv_addr
            and (   self.byte_search < 0
                 or byte_found       == True)
            ):
            self.put_packetbytes(packetByte, 0, len(packetByte)-2, [Ann.SEARCH_CV, ['CV:' + str(self.cv_addr_search)]])
        ## command
        if  (self.command_search != '' 
            and (   (self.command_search.lower() in commandText1.lower())
                 or (self.command_search.lower() in commandText2.lower())
                 or (self.command_search.lower() in commandText3.lower())
                 or (self.command_search.lower() in commandText4.lower())
                 or (self.command_search.lower() in commandText5.lower())
                 or (self.command_search.lower() in commandText6.lower())
            )):
            self.put_packetbytes(packetByte, 0, len(packetByte)-2, [Ann.SEARCH_COMMAND, ['COMMAND:' + (str(self.command_search))]])

        
    def setNextStatus(self, newstatus):
        self.dccStatus     = newstatus
        self.dccBitCounter = 0
        self.decodedBytes  = []
        self.half1Counter  = 0
        if newstatus == 'SYNCRONIZESIGNAL':
            self.syncSignal             = True
            self.railcomCutoutPossible  = False
            self.broken1bitPossible     = False
            self.lastPacketWasStop      = False
        

    def processFoundByte(self, start, stop, data):
        ##[RCN-211 2]
        #Check first bit after synchronization
        if self.dccStatus == 'PREAMBLEFOUND':
            if data == '0':                      #start packet found
                self.putx(start, stop,                     [Ann.FRAME, ['Start Packet', 'Start', 'S']]) #Packet Start Bit
                self.setNextStatus('ADDRESSDATABYTE')
            else:
                self.put_signal(                           [Ann.FRAME_OTHER, ['Resynchronize (Wait for preamble)', 'Resynchronize', 'Resync.', 'R']])
                self.put_signal(                           [Ann.ERROR,       ['unexpected 1-bit found', 'Error', 'E']])
                self.setNextStatus('SYNCRONIZESIGNAL')

        #Wait for the first 1
        elif self.dccStatus == 'WAITINGFORPREAMBLE':
            if data == '1':                      #preamble start
                self.setNextStatus('PREAMBLE')
                self.dccStart      = start

        #Collect the preamble bits
        elif self.dccStatus == 'PREAMBLE':
            if data == '1':                      #preamble bit
                self.dccBitCounter += 1
                self.dccLast       = stop
            else:                                #preamble end
                if     (self.lastPacketWasStop == True
                    and self.timingModeNo != self.timingRCNcomplianceT
                    and self.timingModeNo != self.timingRCNcomplianceS
                    and self.timingModeNo != self.timingNMRAcompliance):
                    self.dccBitCounter += 1
                if self.dccBitCounter+1 >= self.minCountPreambleBits: #valid preamble (minimum 10 bit wherby last stop bit can usually be counted among them)
                    self.putx(start, stop,                     [Ann.FRAME,       ['Start Packet', 'Start', 'S']]) #Packet Start Bit
                    if     (self.lastPacketWasStop == True
                        and self.timingModeNo != self.timingRCNcomplianceT
                        and self.timingModeNo != self.timingRCNcomplianceS
                        and self.timingModeNo != self.timingNMRAcompliance):
                        self.putx(self.dccStart, self.dccLast, [Ann.FRAME,       ['Preamble: 1+' + str(self.dccBitCounter) + ' bits', 'Preamble', 'P']])
                    else:
                        self.putx(self.dccStart, self.dccLast, [Ann.FRAME,       ['Preamble: ' + str(self.dccBitCounter+1) + ' bits', 'Preamble', 'P']])
                    self.setNextStatus('ADDRESSDATABYTE')
                else:                            #invalid preamble
                    self.put_signal(                           [Ann.FRAME_OTHER, ['Resynchronize (Wait for preamble)', 'Resynchronize', 'Resync.', 'R']])
                    if     (self.lastPacketWasStop == True
                        and self.timingModeNo != self.timingRCNcomplianceT
                        and self.timingModeNo != self.timingRCNcomplianceS
                        and self.timingModeNo != self.timingNMRAcompliance):
                        self.putx(self.dccStart, self.dccLast, [Ann.ERROR,       ['Invalid preamble (too few 1-bits (1+' + str(self.dccBitCounter) + '/min' + str(self.minCountPreambleBits) + '))', 'Error', 'E']])
                    else:
                        self.putx(self.dccStart, self.dccLast, [Ann.ERROR,       ['Invalid preamble (too few 1-bits (' + str(self.dccBitCounter+1) + '/min' + str(self.minCountPreambleBits) + '))', 'Error', 'E']])
                    self.setNextStatus('SYNCRONIZESIGNAL')

        #Collection 8 databits and one bit indicating the end of data
        elif self.dccStatus == 'ADDRESSDATABYTE':
            self.lastPacketWasStop = False
            if self.dccBitCounter == 0:          #first bit of new byte
                self.dccValue  = 0
                self.dccBitPos = []
            if self.dccBitCounter < 8:           #build byte 
                self.dccBitPos.append(start)
                self.dccBitCounter += 1
                self.dccValue      = ((self.dccValue) << 1) + int(data)
                if self.dccBitCounter == 8:      #byte complete
                    self.dccBitPos.append(stop)
                    self.decodedBytes.append([self.dccValue, self.dccBitPos])
            else:
                if data == '0':                  #separator to next byte
                    self.dccBitCounter = 0
                    self.dccValue      = 0
                    self.putx(start, stop,                     [Ann.FRAME, ['Start Databyte', 'Start', 'S']])
                else:                            #end identifier
                    self.putx(start, stop,                     [Ann.FRAME, ['Stop Packet', 'Stop', 'S']])
                    self.handleDecodedBytes(self.decodedBytes)
                    self.railcomCutoutPossible = True
                    self.lastPacketWasStop     = True
                    self.setNextStatus('WAITINGFORPREAMBLE')


    def isHalf1Bit(self, sample):
        ##[RCN-210 5 / S-9.1]
        TM    = self.timingModeNo
        TE    = self.timingExperimental
        minTM = minTE = self.timing[TM][self.BIT1MIN]-self.accuracy <= sample
        maxTM = maxTE = sample <= self.timing[TM][self.BIT1MAX]+self.accuracy
        if self.timingCompare == 'on':
            minTE = self.timing[TE][self.BIT1MIN]-self.accuracy <= sample
            maxTE = sample <= self.timing[TE][self.BIT1MAX]+self.accuracy
        if (minTM or minTE) and (maxTM or maxTE):
            if minTM == False and minTE == True:
                v1 = '{:.2f}'.format(sample) + 'µs'
                v2 = '{:.2f}'.format(self.timing[TM][self.BIT1MIN]) + 'µs'
                self.putx(self.edge_1, self.edge_2, [Ann.VARIANCE1, ['half 1 bit to short: actual: ' + v1 + ', minimum: ' + v2, v1 + '/' + v2]])
            elif maxTM == False and maxTE == True:
                v1 = '{:.2f}'.format(sample) + 'µs'
                v2 = '{:.2f}'.format(self.timing[TM][self.BIT1MAX]) + 'µs'
                self.putx(self.edge_1, self.edge_2, [Ann.VARIANCE1, ['half 1 bit to long: actual: ' + v1 + ', maximum: ' + v2, v1 + '/' + v2]])
            return True
        return False
        
    def is1Bit(self, part1, part2):
        ##[RCN-210 5 / S-9.1]
        TM     = self.timingModeNo
        TE     = self.timingExperimental
        minTM1 = minTE1 = self.timing[TM][self.BIT1MIN]-self.accuracy <= part1
        maxTM1 = maxTE1 = part1 <= self.timing[TM][self.BIT1MAX]+self.accuracy
        minTM2 = minTE2 = self.timing[TM][self.BIT1MIN]-self.accuracy <= part2
        maxTM2 = maxTE2 = part2 <= self.timing[TM][self.BIT1MAX]+self.accuracy
        diffTM = diffTE = abs(part1-part2) <= max(self.timing[TM][self.BIT1TOLERANCE], 2*self.accuracy)
        if self.timingCompare == 'on':
            minTE1 = self.timing[TE][self.BIT1MIN]-self.accuracy <= part1
            maxTE1 = part1 <= self.timing[TE][self.BIT1MAX]+self.accuracy
            minTE2 = self.timing[TE][self.BIT1MIN]-self.accuracy <= part2
            maxTE2 = part2 <= self.timing[TE][self.BIT1MAX]+self.accuracy
            diffTE = abs(part1-part2) <= max(self.timing[TE][self.BIT1TOLERANCE], 2*self.accuracy)
        if (    ((minTM1 or minTE1) and (maxTM1 or maxTE1))  #'1' part1
            and ((minTM2 or minTE2) and (maxTM2 or maxTE2))  #'1' part2                 
            and (diffTM or diffTE)                           #difference part1/part2
           ):
            if diffTM == False and diffTE == True:
                v1 = '{:.2f}'.format(abs(part1-part2)) + 'µs'
                v2 = '{:.2f}'.format(self.timing[TM][self.BIT1TOLERANCE]) + 'µs'
                self.put_signal([Ann.VARIANCE2, ['half bits difference: actual: ' + v1 + ', allowed: ' + v2, v1 + '/' + v2]])
            if minTM1 == False and minTE1 == True:
                v1 = '{:.2f}'.format(part1) + 'µs'
                v2 = '{:.2f}'.format(self.timing[TM][self.BIT1MIN]) + 'µs'
                self.putx(self.edge_1, self.edge_2, [Ann.VARIANCE1, ['1. half bit to short: actual: ' + v1 + ', minimum: ' + v2, v1 + '/' + v2]])
            elif maxTM1 == False and maxTE1 == True:
                v1 = '{:.2f}'.format(part1) + 'µs'
                v2 = '{:.2f}'.format(self.timing[TM][self.BIT1MAX]) + 'µs'
                self.putx(self.edge_1, self.edge_2, [Ann.VARIANCE1, ['1. half bit to long: actual: ' + v1 + ', maximum: ' + v2, v1 + '/' + v2]])
            if minTM2 == False and minTE2 == True:
                v1 = '{:.2f}'.format(part2) + 'µs'
                v2 = '{:.2f}'.format(self.timing[TM][self.BIT1MIN]) + 'µs'
                self.putx(self.edge_2, self.edge_3, [Ann.VARIANCE1, ['2. half bit to short: actual: ' + v1 + ', minimum: ' + v2, v1 + '/' + v2]])
            elif maxTM2 == False and maxTE2 == True:
                v1 = '{:.2f}'.format(part2) + 'µs'
                v2 = '{:.2f}'.format(self.timing[TM][self.BIT1MAX]) + 'µs'
                self.putx(self.edge_2, self.edge_3, [Ann.VARIANCE1, ['2. half bit to long: actual: ' + v1 + ', maximum: ' + v2, v1 + '/' + v2]])
            return True
        return False

    def is0Bit(self, part1, part2):
        ##[RCN-210 5 / S-9.1]
        TM       = self.timingModeNo
        TE       = self.timingExperimental
        total    = part1+part2
        minTM1   = minTE1   = self.timing[TM][self.BIT0MIN]-self.accuracy <= part1
        maxTM1   = maxTE1   = part1 <= self.timing[TM][self.BIT0MAX]+self.accuracy
        maxStTM1 = maxStTE1 = part1 <= self.timing[TM][self.BIT0MAXSTRECHED]+self.accuracy
        minTM2   = minTE2   = self.timing[TM][self.BIT0MIN]-self.accuracy <= part2
        maxTM2   = maxTE2   = part2 <= self.timing[TM][self.BIT0MAX]+self.accuracy
        maxStTM2 = maxStTE2 = part2 <= self.timing[TM][self.BIT0MAXSTRECHED]+self.accuracy
        totalTM             = total <= self.BIT0MAXSTRECHEDTOTAL+2*self.accuracy
        withoutStrechedZero = ((self.timingModeNo == self.timingRCNdecoder     and self.rcnAllowStrechedZero == 'no') 
                            or (self.timingModeNo == self.timingRCNcomplianceT and self.rcnAllowStrechedZero == 'no')
                            or (self.timingModeNo == self.timingRCNcomplianceS and self.rcnAllowStrechedZero == 'no')
                            or (self.timingModeNo == self.timingExperimental   and self.rcnAllowStrechedZero == 'no'))

        withStrechedZero    = ((self.timingModeNo == self.timingRCNdecoder     and self.rcnAllowStrechedZero == 'yes') 
                            or (self.timingModeNo == self.timingRCNcomplianceT and self.rcnAllowStrechedZero == 'yes')
                            or (self.timingModeNo == self.timingRCNcomplianceS and self.rcnAllowStrechedZero == 'yes')
                            or (self.timingModeNo == self.timingExperimental   and self.rcnAllowStrechedZero == 'yes')
                            or (self.timingModeNo == self.timingNMRAdecoder)
                            or (self.timingModeNo == self.timingNMRAcompliance))
        if self.timingCompare == 'on':
            minTE1   = self.timing[TE][self.BIT0MIN]-self.accuracy <= part1
            maxTE1   = part1 <= self.timing[TE][self.BIT0MAX]+self.accuracy
            maxStTE1 = part1 <= self.timing[TE][self.BIT0MAXSTRECHED]+self.accuracy
            minTE2   = self.timing[TE][self.BIT0MIN]-self.accuracy <= part2
            maxTE2   = part2 <= self.timing[TE][self.BIT0MAX]+self.accuracy
            maxStTE2 = part2 <= self.timing[TE][self.BIT0MAXSTRECHED]+self.accuracy
        if (    (    withoutStrechedZero
                 and ((minTM1 or minTE1) and (maxTM1 or maxTE1))      #'0' part1
                 and ((minTM2 or minTE2) and (maxTM2 or maxTE2))      #'0' part2
                )
                or
                (    withStrechedZero
                 and ((minTM1 or minTE1) and (maxStTM1 or maxStTE1))  #'0' part1
                 and ((minTM2 or minTE2) and (maxStTM2 or maxStTE2))  #'0' part2
                 and totalTM                                          #'0' max part1+part2
                )
            ):
            if minTM1 == False and minTE1 == True:
                v1 = '{:.2f}'.format(part1) + 'µs'
                v2 = '{:.2f}'.format(self.timing[TM][self.BIT0MIN]) + 'µs'
                self.putx(self.edge_1, self.edge_2, [Ann.VARIANCE1, ['1. half bit to short: actual: ' + v1 + ', minimum: ' + v2, v1 + '/' + v2]])
            if minTM2 == False and minTE2 == True:
                v1 = '{:.2f}'.format(part2) + 'µs'
                v2 = '{:.2f}'.format(self.timing[TM][self.BIT0MIN]) + 'µs'
                self.putx(self.edge_2, self.edge_3, [Ann.VARIANCE1, ['2. half bit to short: actual: ' + v1 + ', minimum: ' + v2, v1 + '/' + v2]])
            if withoutStrechedZero:
                if maxTM1 == False and maxTE1 == True:
                    v1 = '{:.2f}'.format(part1) + 'µs'
                    v2 = '{:.2f}'.format(self.timing[TM][self.BIT0MAX]) + 'µs'
                    self.putx(self.edge_1, self.edge_2, [Ann.VARIANCE1, ['1. half bit to long: actual: ' + v1 + ', maximum: ' + v2, v1 + '/' + v2]])
                elif maxTM2 == False and maxTE2 == True:
                    v1 = '{:.2f}'.format(part2) + 'µs'
                    v2 = '{:.2f}'.format(self.timing[TM][self.BIT0MAX]) + 'µs'
                    self.putx(self.edge_2, self.edge_3, [Ann.VARIANCE1, ['2. half bit to long: actual: ' + v1 + ', maximum: ' + v2, v1 + '/' + v2]])
            if withStrechedZero:
                if maxStTM1 == False and maxStTE1 == True:
                    v1 = '{:.2f}'.format(part1) + 'µs'
                    v2 = '{:.2f}'.format(self.timing[TM][self.BIT0MAXSTRECHED]) + 'µs'
                    self.putx(self.edge_1, self.edge_2, [Ann.VARIANCE1, ['1. half bit to long: actual: ' + v1 + ', maximum: ' + v2, v1 + '/' + v2]])
                if maxStTM2 == False and maxStTE2 == True:
                    v1 = '{:.2f}'.format(part2) + 'µs'
                    v2 = '{:.2f}'.format(self.timing[TM][self.BIT0MAXSTRECHED]) + 'µs'
                    self.putx(self.edge_2, self.edge_3, [Ann.VARIANCE1, ['2. half bit to long: actual: ' + v1 + ', maximum: ' + v2, v1 + '/' + v2]])
            return True
        return False

    def isStreched0Bit(self, part1, part2):
        TM    = self.timingModeNo
        TE    = self.timingExperimental
        maxTM = maxTE = max(self.timing[TM][self.BIT1TOLERANCE], 2*self.accuracy)
        if self.timingCompare == 'on':
            maxTE = max(self.timing[TE][self.BIT1TOLERANCE], 2*self.accuracy)
        if abs(part1-part2) > (maxTM or maxTE):  #BIT1TOLERANCE used
            return True
        return False

    def isRailcomCutout(self, sample):
        ##[RCN-217 2.4]
        TM = self.timingModeNo
        if (     self.timingModeNo != self.timingNMRAcompliance
             and self.timingModeNo != self.timingRCNcomplianceT
             and self.timingModeNo != self.timingRCNcomplianceS
             and self.railcomCutoutPossible == True                                                                                   #only next to stopbit
             and self.RAILCOMCUTOUTMIN-self.accuracy <= sample <= (self.RAILCOMCUTOUTMAX + 2*(self.timing[TM][self.BIT1MAX]+self.accuracy) )
           ):
            return True
        return False

    def isBroken1BitAfterRailcomCutout(self, total):
        ##[RCN-217 2.4]
        TM = self.timingModeNo
        if (    self.broken1bitPossible == True
            and total <= self.timing[TM][self.BIT1MAX]+self.accuracy 
            ):
            return True
        return False


    def decode(self):
        if self.samplerate is None:
            raise SamplerateError('Cannot decode without samplerate')
        if self.samplerate <= 0:
            raise SamplerateError('Cannot decode with samplerate 0 or less')

        #initialize
        self.half1Counter = 0
        self.wait({0: 'e'})
        self.edge_1     = self.samplenum
        self.wait({0: 'e'})
        self.edge_2     = self.samplenum

        #set accuracy
        if self.timingModeNo == self.timingExperimental and self.ExpAccurancy >= 0:
            self.accuracy = self.ExpAccurancy
        else:
            self.accuracy = 1/self.samplerate*1000000  #µs (self.accuracy is depending on sample rate, it is about recognizing a packet, not checking the correct timing)
        
        #Info at the start
        output_1      = 'Samplerate: '
        if self.samplerate/1000 < 1000:
            output_1 += '{:.0f}'.format(self.samplerate/1000) + ' kHz'
        else:
            output_1 += '{:.0f}'.format(self.samplerate/1000000) + ' MHz'
        output_1     += ', this results in an accuracy deviation of: '    
        if self.accuracy >= 1:
            output_1 += '{:.0f}'.format(self.accuracy) + ' µs'
        else:
            output_1 += '{:.0f}'.format(self.accuracy*1000) + ' ns'
        output_1 += ", DCC decoder version:" + self.version
        self.putx(0, self.edge_1, [Ann.BITS_OTHER, [output_1]])

        while True:
            '''
                             ______        ____________              ______
            signal        __|      |______|            |____________|      |__
                            ^      ^      ^            ^            ^      ^
            edge            1      2      3            4
            edge next run                 1            2            3      4
                            |part 1|part 2|   part 1   |   part 2   |part 1|
                            |    total    |          total          |
            '''
            self.edge_0 = self.edge_1
            self.edge_3 = None
            self.edge_4 = None
            value       = '?'
            value_short = '?'
            part1       = (self.edge_2-self.edge_1)/self.samplerate*1000000 #µs

            ## error-messages
            output_1 = ''
            if self.samplerate < 25000:
                output_1 = 'Samplerate must be >= 25kHz'
            if (self.timingModeNo == self.timingINVALID): 
                output_1 = 'Samplerate too inaccurate for compliance testing: Please use at least 2Mhz'
            if (self.options['Search_acc_addr'] != '' and self.acc_addr_search == -255):
                output_1 = 'Search: accessory address invalid (use 1-2048)';
            if (self.options['Search_dec_addr'] != '' and self.dec_addr_search == -255):
                output_1 = 'Search: decoder address invalid (use 0-10239)';
            if (self.options['Search_cv'] != '' and self.cv_addr_search == -255):
                output_1 = 'Search: CV address invalid (use 1-16777216)';
            if (self.options['Search_byte'] != '' and self.byte_search == -255):
                output_1 = 'Search: invalid byte value (use 0-255 or 0b00000000-0b11111111 or 0x00-0xff)';
            if ((self.timingModeNo == self.timingNMRAcompliance or self.timingModeNo == self.timingRCNcomplianceT or self.timingModeNo == self.timingRCNcomplianceS) and self.preambleBitsCount < 10):
                output_1 = '"compliance mode: min. preamble bits" must be greater than 9';
            if ((self.timingModeNo == self.timingExperimental or self.timingCompare == 'on') and self.B1min < 0):
                output_1 = 'Exp: invalid value: "1-bit half min." must be greater than 0';
            if ((self.timingModeNo == self.timingExperimental or self.timingCompare == 'on') and self.B1max < 0):
                output_1 = 'Exp: invalid value: "1-bit half max." must be greater than 0';
            if ((self.timingModeNo == self.timingExperimental or self.timingCompare == 'on') and self.B1min > self.B1max):
                output_1 = 'Exp: invalid value: "1-bit half min." is greater "1-bit half max."';
            if ((self.timingModeNo == self.timingExperimental or self.timingCompare == 'on') and self.B1tolerance < 0):
                output_1 = 'Exp: invalid value: "1-bit tolerance" must be greater than 0';
            if ((self.timingModeNo == self.timingExperimental or self.timingCompare == 'on') and self.B0min < 0):
                output_1 = 'Exp: invalid value: "0-bit half min." must be greater than 0';
            if ((self.timingModeNo == self.timingExperimental or self.timingCompare == 'on') and self.B0max < 0):
                output_1 = 'Exp: invalid value: "0-bit half max." must be greater than 0';
            if ((self.timingModeNo == self.timingExperimental or self.timingCompare == 'on') and self.B0min > self.B0max):
                output_1 = 'Exp: invalid value: "0-bit half min." is greater "0-bit half max."';
            if ((self.timingModeNo == self.timingExperimental or self.timingCompare == 'on') and self.B0max_streched < 0):
                output_1 = 'Exp: invalid value: "0-bit streched" must be greater than 0';
            if ((self.timingModeNo == self.timingExperimental or self.timingCompare == 'on') and self.B0min > self.B0max_streched):
                output_1 = 'Exp: invalid value: "0-bit half min." is greater "0-bit streched"';
            if ((self.timingModeNo == self.timingExperimental or self.timingCompare == 'on') and self.B0max > self.B0max_streched):
                output_1 = 'Exp: invalid value: "0-bit half max." is greater "0-bit streched"';

            if not output_1 == '':
                self.wait({'skip': 99}) #arbitrarily chosen value
                self.edge_3 = self.samplenum
                self.put_signal([Ann.ERROR, [output_1, 'Error', 'E']])
                self.wait({0: 'e'})
                self.edge_1 = self.edge_3
                self.edge_2 = self.samplenum
                continue


            ## Synchronization: search for preamble 
            if self.dccStatus  == 'SYNCRONIZESIGNAL':
                # half '1'?
                if self.isHalf1Bit(part1):
                    self.half1Counter += 1
                    self.putx(self.edge_1, self.edge_2, [Ann.BITS_OTHER,  ['half 1 bit', '½ 1']])
                    self.putx(self.edge_1, self.edge_2, [Ann.FRAME_OTHER, ['Synchronize (' + str(self.half1Counter) + '/min' + str(self.minCountPreambleBits*2) + ')', 'Sync', 'S']])
                    self.edge_0 = self.edge_1
                    self.edge_1 = self.edge_2
                    self.wait({0: 'e'})
                    self.edge_2 = self.samplenum
                    continue
                    
                # <> half '1'    
                else:
                    self.wait({0: 'e'})
                    self.edge_3     = self.samplenum
                    part2 = (self.edge_3-self.edge_2)/self.samplerate*1000000 #µs
                    total = part1+part2

                    # '0' bit?
                    if self.is0Bit(part1, part2):
                        # valid preamble found?
                        if self.half1Counter >= (self.minCountPreambleBits*2):
                            self.syncSignal   = False
                            self.half1Counter = 0
                            self.setNextStatus('PREAMBLEFOUND')
                        # no valid preamble
                        else:
                            if self.half1Counter == 0:
                                self.putx(self.edge_1, self.edge_2, [Ann.FRAME_OTHER, ['Synchronize (wait for half 1 bits)', 'Synchronize', 'Sync', 'S']])
                                self.putx(self.edge_2, self.edge_3, [Ann.FRAME_OTHER, ['Synchronize (wait for half 1 bits)', 'Synchronize', 'Sync', 'S']])
                            else:
                                self.putx(self.edge_1, self.edge_3, [Ann.BITS_OTHER,  ['0']])
                                self.putx(self.edge_1, self.edge_3, [Ann.FRAME_OTHER, ['Synchronize (wait for preamble) (too few half 1 bits (' + '{:.0f}'.format(self.half1Counter) + '/min' + '{:.0f}'.format(self.minCountPreambleBits*2) + '))', 'Synchronize', 'Sync.', 'S']])
                            self.half1Counter = 0
                            self.wait({0: 'e'})
                            self.edge_1 = self.edge_3
                            self.edge_2 = self.samplenum
                            continue
                            
                    # invalid/unknown timing
                    else:
                        self.putx(self.edge_1, self.edge_2, [Ann.BITS_OTHER,  ['{:.2f}'.format(part1) + 'µs']])
                        self.putx(self.edge_1, self.edge_2, [Ann.FRAME_OTHER, ['Synchronize (wait for half 1 bits)', 'Sync', 'S']])
                        self.edge_1     = self.edge_2
                        self.edge_2     = self.edge_3
                        self.setNextStatus('SYNCRONIZESIGNAL')
                        continue
            ## No synchronization            
            else:
                self.wait({0: 'e'})
                self.edge_3     = self.samplenum
                part2 = (self.edge_3-self.edge_2)/self.samplerate*1000000 #µs
                total = part1+part2

                
            ## 1-Bit?
            if self.is1Bit(part1, part2):
                value = '1'
                self.railcomCutoutPossible = False
                self.broken1bitPossible    = False

            ## 0-Bit?
            elif self.is0Bit(part1, part2):
                value = '0'
                ## could be a railcom cutout?
                if self.isRailcomCutout(total):
                    self.railcomCutoutPossible  = False
                    self.broken1bitPossible     = True
                    self.lastPacketWasStop      = False
                    self.put_signal([Ann.BITS, ['Railcom cutout', 'Railcom', 'R']])
                    self.wait({0: 'e'})
                    self.edge_1 = self.edge_3
                    self.edge_2 = self.samplenum
                    self.setNextStatus('WAITINGFORPREAMBLE')
                    continue
                self.railcomCutoutPossible = False
                self.broken1bitPossible    = False
                if self.isStreched0Bit(part1, part2):
                    TM = self.timingModeNo
                    self.put_signal([Ann.INFO, ['Streched 0-bit: Δ:' + '{:.2f}'.format(abs(part1-part2)) + 'µs (' + '{:.2f}'.format(part1) + 'µs/' + '{:.2f}'.format(part2) + 'µs)', 'Δ' + '{:.2f}'.format(abs(part1-part2)) + 'µs']])

            ## Railcomcutout?
            elif self.isRailcomCutout(total):
                self.railcomCutoutPossible  = False
                self.broken1bitPossible     = True
                self.lastPacketWasStop      = False
                self.put_signal([Ann.BITS, ['Railcom cutout', 'Railcom', 'R']])
                self.wait({0: 'e'})
                self.edge_1 = self.edge_3
                self.edge_2 = self.samplenum
                self.setNextStatus('WAITINGFORPREAMBLE')
                continue

            ## broken 1-bit next to railcom cutout?
            elif self.isBroken1BitAfterRailcomCutout(total):
                self.broken1bitPossible = False
                self.putx(self.edge_1, self.edge_3, [Ann.FRAME_OTHER, ['broken 1-bit']])
                self.putx(self.edge_1, self.edge_3, [Ann.BITS_OTHER,  ['ignored broken 1-bit after Railcom cutout', 'ignored']])
                self.wait({0: 'e'})
                self.edge_1 = self.edge_3
                self.edge_2 = self.samplenum
                self.setNextStatus('WAITINGFORPREAMBLE')
                continue

            ## unknown timing
            else:
                # filter out short pulses
                if self.ignoreInterferingPulse == 'yes':
                    self.wait({0: 'e'})
                    self.edge_4     = self.samplenum  #Look into the future to filter out short pulses (see below)
                    output_1 = 'Short pulse ignored'
                    if      (self.edge_4 - self.edge_3)/self.samplerate*1000000 <= self.maxInterferingPulseWidth\
                        and (self.edge_3 - self.edge_2)/self.samplerate*1000000 <= self.maxInterferingPulseWidth:
                        self.edge_2 = int((self.edge_2 + self.edge_4) / 2) #not quite accurate but sufficient enough
                        self.putx(self.edge_2, self.edge_4, [Ann.INFO, [output_1 + ' (1)']])
                        continue
                    elif (self.edge_4 - self.edge_3)/self.samplerate*1000000 <= self.maxInterferingPulseWidth:
                        self.putx(self.edge_3, self.edge_4, [Ann.INFO, [output_1 + ' (2)']])
                        continue
                    elif (self.edge_3 - self.edge_2)/self.samplerate*1000000 <= self.maxInterferingPulseWidth: 
                        self.putx(self.edge_2, self.edge_3, [Ann.INFO, [output_1 + ' (3)']])
                        self.edge_2     = self.edge_4
                        continue
                        
                # unknown timing
                value       = '{:.2f}'.format(total) + 'µs=' + '{:.2f}'.format(part1) + 'µs+' + '{:.2f}'.format(part2) + 'µs'
                value_short = '{:.2f}'.format(total) + 'µs'
                self.put_signal([Ann.FRAME_OTHER, ['Resynchronize (wait for preamble)', 'Resynchronize', 'Resync.', 'R']])
                self.put_signal([Ann.ERROR,       ['unknown timing - should not occur - dirty signal?', 'Error', 'E']])
                self.setNextStatus('SYNCRONIZESIGNAL')


            if value not in ['0', '1']:
                self.put_signal([Ann.BITS_OTHER, [value, value_short]])
                self.setNextStatus('SYNCRONIZESIGNAL')
            elif self.dccStatus != 'SYNCRONIZESIGNAL':
                self.put_signal([Ann.BITS,       [value]])
                self.processFoundByte(self.edge_1, self.edge_3, value)


            if self.edge_4 == None:
                self.wait({0: 'e'})
                self.edge_4 = self.samplenum
            
            self.edge_1     = self.edge_3
            self.edge_2     = self.edge_4
            