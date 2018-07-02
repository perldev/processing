# -*- coding: utf-8 -*-
 
# Copyright 2011 Álvaro Justen [alvarojusten at gmail dot com]
# License: GPL <http://www.gnu.org/copyleft/gpl.html>
 
from PIL import Image
from PIL import ImageDraw
from PIL import  ImageFont
import StringIO

from PIL import ImageFilter
from random import randint, choice
import  random
import math
import random
'1f2bde3ac'
class WigglyBlocks(object):
    """Randomly select and shift blocks of the image"""
    def __init__(self, blockSize=16, sigma=0.01, iterations=300):
        self.blockSize = blockSize
        self.sigma = sigma
        self.iterations = iterations
        self.seed = random.random()

    def render(self, image):
        r = random.Random(self.seed)
        for i in xrange(self.iterations):
            # Select a block
            bx = int(r.uniform(0, image.size[0]-self.blockSize))
            by = int(r.uniform(0, image.size[1]-self.blockSize))
            block = image.crop((bx, by, bx+self.blockSize-1, by+self.blockSize-1))

            # Figure out how much to move it.
            # The call to floor() is important so we always round toward
            # 0 rather than to -inf. Just int() would bias the block motion.
            mx = int(math.floor(r.normalvariate(0, self.sigma)))
            my = int(math.floor(r.normalvariate(0, self.sigma)))

            # Now actually move the block
            image.paste(block, (bx+mx, by+my))


class WarpBase(object):
    """Abstract base class for image warping. Subclasses define a
       function that maps points in the output image to points in the input image.
       This warping engine runs a grid of points through this transform and uses
       PIL's mesh transform to warp the image.
       """
    filtering = Image.BILINEAR
    resolution = 10

    def getTransform(self, image):
        """Return a transformation function, subclasses should override this"""
        return lambda x, y: (x, y)

    def render(self, image):
        r = self.resolution
        xPoints = image.size[0] / r + 2
        yPoints = image.size[1] / r + 2
        f = self.getTransform(image)

        # Create a list of arrays with transformed points
        xRows = []
        yRows = []
        for j in xrange(yPoints):
            xRow = []
            yRow = []
            for i in xrange(xPoints):
                x, y = f(i*r, j*r)

                # Clamp the edges so we don't get black undefined areas
                x = max(0, min(image.size[0]-1, x))
                y = max(0, min(image.size[1]-1, y))

                xRow.append(x)
                yRow.append(y)
            xRows.append(xRow)
            yRows.append(yRow)

        # Create the mesh list, with a transformation for
        # each square between points on the grid
        mesh = []
        for j in xrange(yPoints-1):
            for i in xrange(xPoints-1):
                mesh.append((
                    # Destination rectangle
                    (i*r, j*r,
                     (i+1)*r, (j+1)*r),
                    # Source quadrilateral
                    (xRows[j  ][i  ], yRows[j  ][i  ],
                     xRows[j+1][i  ], yRows[j+1][i  ],
                     xRows[j+1][i+1], yRows[j+1][i+1],
                     xRows[j  ][i+1], yRows[j  ][i+1]),
                    ))

        return image.transform(image.size, Image.MESH, mesh, self.filtering)


class SineWarp(WarpBase):
    """Warp the image using a random composition of sine waves"""

    def __init__(self,
                 amplitudeRange = (3, 6.5),
                 periodRange    = (0.04, 0.1),
                 ):
        self.amplitude = random.uniform(*amplitudeRange)
        self.period = random.uniform(*periodRange)
        self.offset = (random.uniform(0, math.pi * 2 / self.period),
                       random.uniform(0, math.pi * 2 / self.period))

    def getTransform(self, image):
        return (lambda x, y,
                a = self.amplitude,
                p = self.period,
                o = self.offset:
                (math.sin( (y+o[0])*p )*a + x,
                 math.sin( (x+o[1])*p )*a + y))


def render(image, filename):
        
        obj =  SineWarp()
        obj1 = WigglyBlocks()
        img = obj.render(image)
        #obj1.render(img)
        img.save(filename)


def pin(filename):
    Keys = 'WERTYUIPLKJHGFDSAZXCVBNM1234567890'    
    key = ''.join( [choice( Keys ) for i in xrange(5)] )
    
    img = Image.new('RGB', (400,120), 0xE0EEE0 )
    draw = ImageDraw.Draw(img)
    
    for i in xrange(8):
        draw.line( [(randint(0,400),randint(0,120)),(randint(0,400),randint(0,120))] ,  randint(0, 0x000000), 2)
    
    font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMono.ttf', 124)
    draw.text( (0,0), key, 0, font)    
    f = StringIO.StringIO()
    img.save(f, "PNG")
    raw = f.getvalue()
    render(img, filename)    
    
    array = []
    HasKeys = {}
    for letter in Keys:
           HasKeys[letter] = 1 
           
    for i in key:
            char1 = chr(ord(i) + 1)
            if HasKeys.has_key(char1) :
                array.append(char1)
                
            array.append(i)
            
    return  (''.join(random.sample(array,len(array))), key)
    
    

def draw_text( text, filename):

    
    img = Image.new('RGB', (80,60), 0xffffff )
    draw = ImageDraw.Draw(img)
    
    for i in xrange(6):
        draw.line( [(randint(0,80),randint(0,60)),(randint(0,80),randint(0,60))] ,  randint(0, 0x000000), 2)
        
    font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMono.ttf', 64)
    draw.text( (10,0), text, 0, font)   
    f = StringIO.StringIO()
    img.save(f, "PNG")
    raw = f.getvalue()
    render(img, "pins_images/"+filename)    
    return True
 
 
class ImageText(object):
    def __init__(self, filename_or_size, mode='RGBA', background=(0, 0, 0, 0),
                 encoding='utf8'):
            
        if isinstance(filename_or_size, str):
            self.filename = filename_or_size
            self.image = Image.open(self.filename)
            self.size = self.image.size
            
        elif isinstance(filename_or_size, (list, tuple)):
            self.size = filename_or_size
            self.image = Image.new(mode, self.size, color=background)
            self.filename = None
        self.draw = ImageDraw.Draw(self.image)
        self.encoding = encoding
    def filt(self, Filter):
        self.image.filter(Filter)   
 
    def save(self, filename=None):
        self.image.save(filename or self.filename)
 
    def get_font_size(self, text, font, max_width=None, max_height=None):
        if max_width is None and max_height is None:
            raise ValueError('You need to pass max_width or max_height')
        font_size = 1
        text_size = self.get_text_size(font, font_size, text)
        if (max_width is not None and text_size[0] > max_width) or \
           (max_height is not None and text_size[1] > max_height):
            raise ValueError("Text can't be filled in only (%dpx, %dpx)" % \
                    text_size)
        while True:
            if (max_width is not None and text_size[0] >= max_width) or \
               (max_height is not None and text_size[1] >= max_height):
                return font_size - 1
            font_size += 1
            text_size = self.get_text_size(font, font_size, text)
 
    def write_text(self, (x, y), text, font_filename, font_size=11,
                   color=(0, 0, 0), max_width=None, max_height=None):
        if isinstance(text, str):
            text = text.decode(self.encoding)
        if font_size == 'fill' and \
           (max_width is not None or max_height is not None):
            font_size = self.get_font_size(text, font_filename, max_width,
                                           max_height)
        text_size = self.get_text_size(font_filename, font_size, text)
        font = ImageFont.truetype(font_filename, font_size)
        if x == 'center':
            x = (self.size[0] - text_size[0]) / 2
        if y == 'center':
            y = (self.size[1] - text_size[1]) / 2
        self.draw.text((x, y), text, font=font, fill=color)
        return text_size
 
    def get_text_size(self, font_filename, font_size, text):
        font = ImageFont.truetype(font_filename, font_size)
        return font.getsize(text)
 
    def write_text_box(self, (x, y), text, box_width, font_filename,
                       font_size=11, color=(0, 0, 0), place='left',
                       justify_last_line=False):
        lines = []
        line = []
        words = text.split()
        for word in words:
            new_line = ' '.join(line + [word])
            size = self.get_text_size(font_filename, font_size, new_line)
            text_height = size[1]
            if size[0] <= box_width:
                line.append(word)
            else:
                lines.append(line)
                line = [word]
        if line:
            lines.append(line)
        lines = [' '.join(line) for line in lines if line]
        height = y
        for index, line in enumerate(lines):
            height += text_height
            if place == 'left':
                self.write_text((x, height), line, font_filename, font_size,
                                color)
            elif place == 'right':
                total_size = self.get_text_size(font_filename, font_size, line)
                x_left = x + box_width - total_size[0]
                self.write_text((x_left, height), line, font_filename,
                                font_size, color)
            elif place == 'center':
                total_size = self.get_text_size(font_filename, font_size, line)
                x_left = int(x + ((box_width - total_size[0]) / 2))
                self.write_text((x_left, height), line, font_filename,
                                font_size, color)
            elif place == 'justify':
                words = line.split()
                if (index == len(lines) - 1 and not justify_last_line) or \
                   len(words) == 1:
                    self.write_text((x, height), line, font_filename, font_size,
                                    color)
                    continue
                line_without_spaces = ''.join(words)
                total_size = self.get_text_size(font_filename, font_size,
                                                line_without_spaces)
                space_width = (box_width - total_size[0]) / (len(words) - 1.0)
                start_x = x
                for word in words[:-1]:
                    self.write_text((start_x, height), word, font_filename,
                                    font_size, color)
                    word_size = self.get_text_size(font_filename, font_size,
                                                    word)
                    start_x += word_size[0] + space_width
                last_word_size = self.get_text_size(font_filename, font_size,
                                                    words[-1])
                last_word_x = x + box_width - last_word_size[0]
                self.write_text((last_word_x, height), words[-1], font_filename,
                                font_size, color)
        return (box_width, height - y)
