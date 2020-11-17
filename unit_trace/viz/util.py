#!/usr/bin/python

"""Miscellanious utility functions that don't fit anywhere."""

def format_float(num, numplaces):
    if abs(round(num, numplaces) - round(num, 0)) == 0.0:
        return '%.0f' % float(num)
    else:
        return ('%.' + numplaces + 'f') % round(float(num), numplaces)
