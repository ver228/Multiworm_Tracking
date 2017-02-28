# -*- coding: utf-8 -*-
"""
Created on Fri May 22 18:10:04 2015

@author: ajaver
"""

from .cython_files.cleanWorm_cython import extremaPeaksCircDist, removeSmallSegments, cleanContour
from .cython_files.circCurvature import circCurvature

import numpy as np


def circCurvature_old(points, edgeLength):
    '''
    TODO: This is the help from segworm, it must be changed, particularly copyright...
    %CIRCCURVATURE Compute the curvature for a clockwise, circularly-connected
    %vector of points.
    %
    %   ANGLES = CIRCCURVATURE(POINTS, EDGELENGTH)
    %
    %   ANGLES = CIRCCURVATURE(POINTS, EDGELENGTH, CHAINCODELENGTHS)
    %
    %   Inputs:
    %       points           - the vector of clockwise, circularly-connected
    %                          points ((x,y) pairs).
    %       edgeLength       - the length of edges from the angle vertex.
    %       chainCodeLengths - the chain-code length at each point;
    %                          if empty, the array indices are used instead
    %   Output:
    %       angles - the angles of curvature per point (0 = none to +-180 =
    %                maximum curvature). The sign represents whether the angle
    %                is convex (+) or concave (-).
    %
    % See also CURVATURE, CIRCCOMPUTECHAINCODELENGTHS
    %
    %
    % © Medical Research Council 2012
    % You will not remove any copyright or other notices from the Software;
    % you must reproduce all copyright notices and other proprietary
    % notices on any copies of the Software.'''
#%%
    edgeLength = int(edgeLength)
    #% Initialize the edges.
    p1 = np.roll(points, edgeLength, axis=0)
    p2 = np.roll(points, -edgeLength, axis=0)

    t2 = np.arctan2(points[:, 0] - p2[:, 0], points[:, 1] - p2[:, 1])
    t1 = np.arctan2(p1[:, 0] - points[:, 0], p1[:, 1] - points[:, 1])
    #% Use the difference in tangents to measure the angle.
    angles = t2 - t1
    angles[angles > np.pi] -= 2 * np.pi
    angles[angles < -np.pi] += 2 * np.pi
    angles = angles * 180 / np.pi
#%%
    return angles


def circConv(a, b):
    '''
    TODO: This is the help from segworm, it must be changed, particularly copyright...
    %CIRCCONV Convolve the circularly connected vector a with b.
    %
    %   [C] = CIRCCONV(A, B)
    %
    %   Inputs:
    %       a - a circularly connected vector
    %       b - the vector to convolve with a
    %
    %   Outputs:
    %       c - the convolution of the circularly connected vector a with b
    %
    %
    % © Medical Research Council 2012
    % You will not remove any copyright or other notices from the Software;
    % you must reproduce all copyright notices and other proprietary
    % notices on any copies of the Software.'''

    assert a.size > b.size  # maybe it would be better to replace with a warning

    #% Wrap the ends of A and convolve with B.
    wrapSize = int(np.ceil(b.size / 2))

    wrapA = np.lib.pad(a, (wrapSize, wrapSize), 'wrap')
    wrapA = np.convolve(wrapA, b, 'same')

    #% Strip away the wrapped ends of A.
    # return wrapA[wrapSize+1:wrapA.size-wrapSize+1]
    return wrapA[wrapSize:-wrapSize]
    # segworm returns this, I think it might more correct
    # to use wrapA[wrapSize:-wrapSize], but there might be a reason so i leave
    # it like this


def circSmooth(angles, blurLength):
    if blurLength > 1:
        blurWin = np.empty(int(blurLength))
        blurWin.fill(1. / blurLength)
        return circConv(angles, blurWin)
    else:
        return angles


def getPossibleConnections(worm_contour, maxI, minI, nearSize):
    #%%
    # TODO There is a bug in this function, where the size of the array conns
    # is too small to hold all "posible connections"

    #% Connect sharp convexities that are nearby on the contour and/or,
    #% nearby in distance and separated by a sharp concavity.
    #% Note: the worm's width is approximately the size of a muscle segment.
    #% Binarization may yield a split with diagonally-offset, forking
    #% convexities. Therefore, 2 segments is a good size to bound the
    #% distance between nearby, split convexities.
    #% Note 2: the connections are organized as the vector triplet:
    #% [startContourIndex endContourIndex isWrapping]
    #% Contour points between startContourIndex and endContourIndex are removed.
    conns = np.zeros((maxI.size, 4))
    connsI = 0  # % the current index for connections
    for i in range(0, (maxI.size - 1)):
        #% Are there any sharp convexities nearby?
        for j in range(i + 1, maxI.size):
            R = np.sqrt(
                np.sum(
                    (worm_contour[
                        maxI[i],
                        :] -
                        worm_contour[
                        maxI[j],
                        :])**2))
            if R <= nearSize:
                #% Which side is shorter?
                #% Side1 is continuous and goes from start (iI) to end (jI)
                #% in positive, index increments.
                #% Side2 wraps and always goes from start (iI) to end (jI)
                #% in negative, index increments.
                iI = maxI[i]
                jI = maxI[j]
                dSide1 = jI - iI  # % The continuous side is shorter.
                # % The wrapping side is shorter so check it instead.
                dSide2 = iI + worm_contour.shape[0] - jI

                if dSide1 < dSide2:
                    #% The continuous side is shorter.
                    #% Is the convexity nearby on the contour.
                    if dSide1 <= nearSize:
                        conns[connsI, :] = np.array((iI, jI, 0, dSide1))
                        connsI += 1
                    #% Is there a concavity separating us on our shorter,
                    #% continuous side?
                    else:
                        for mini in minI:
                            if mini > iI and mini < jI:
                                conns[connsI, :] = np.array(
                                    (iI, jI, 0, dSide1))
                                connsI += 1
                                break
                else:
                    #% The wrapping side is shorter so check it instead.
                    if dSide2 <= nearSize:
                        conns[connsI, :] = np.array((jI, iI, 1, dSide2))
                        connsI += 1
                    #% Is there a concavity separating us on our shorter,
                    #% continuous side?
                    else:
                        for mini in minI:
                            if mini < iI or mini > jI:
                                conns[connsI, :] = np.array(
                                    (jI, iI, 1, dSide2))
                                connsI += 1
                                break

    conns = conns[:connsI, :].copy()
    if conns.shape[0] > 1:
        #% Sort the connections by size if there is more than one
        conns = conns[conns[:, -1].argsort(), ]

    return conns


def connectPeaks(conns, maxI):
    #%%

    #% Connect the peaks until there are at least 2 left.
    numPeaks = maxI.size
    if numPeaks > 2 and conns.shape[0] >= 2:
        peaks_index = np.zeros((numPeaks))
        peaks_label = np.zeros((numPeaks))
        peaks_index[0:2] = conns[0, 0:2]  # % connect the peaks
        peaks_label[0:2] = 1  # % label the new, unique peak connection
        j = 2  # % the peaks index
        label = 2  # % the unique peak label index
        numPeaks = numPeaks - 1  # % the number of unique peaks
        i = 1  # % the conns index
        while numPeaks > 2 and i < conns.shape[0]:
            #% Are either of the peaks new?
            peak1_label = peaks_label[peaks_index[0:j] == conns[i, 0]]
            peak2_label = peaks_label[peaks_index[0:j] == conns[i, 1]]

            #% Both peaks are new.
            if peak1_label.size == 0:
                if peak2_label.size == 0:
                    peaks_index[j:(j + 2)] = conns[i, 0:2]
                    peaks_label[j:(j + 2)] = label
                    j = j + 2
                    label = label + 1

                #% The first peak is new.
                else:
                    peaks_index[j] = conns[i, 0]
                    peaks_label[j] = peak2_label[0]
                    j += 1

                #% We lost a peak to the connection.
                numPeaks -= 1

            #% The second peak is new.
            elif peak2_label.size == 0:
                peaks_index[j] = conns[i, 1]
                peaks_label[j] = peak1_label[0]
                j = j + 1
                #% We lost a peak to the connection.
                numPeaks -= 1
            #% Relabel the second peak and its connections.
            elif peak1_label < peak2_label:
                peaks_label[peaks_label[0:j] == peak2_label] = peak1_label
                #% We lost a peak to the connection.
                numPeaks -= 1
            #% Relabel the first peak and its connections.
            elif peak1_label > peak2_label:
                peaks_label[peaks_label[0:j] == peak1_label] = peak2_label
                #% We lost a peak to the connection.
                numPeaks -= 1

            #% Advance.
            i += 1
        conns = conns[:i + 1, :]
#%%
    return conns


def connectConnections(conns):
    if conns.shape[0] == 0:
        return conns
#%%
    #% Connect the connections.
    prevConnsSize = conns.shape[0]
    newConnsI = 0  # % the current index for new connections
    #conns_ori = conns.copy()
    while newConnsI < prevConnsSize:
        # % the new connections (pre-allocate memory)
        newConns = np.zeros((2 * conns.shape[0], 3))
        # print newConns.shape
        newConnsI = 0
        for i in range(conns.shape[0]):
            connected = False  # % have we made any connections?
            for j in range(i + 1, conns.shape[0]):
                #% Are both connections continuous?
                if not conns[i, 2]:
                    if not conns[j, 2]:
                        #% Does connection j intersect i?
                        if conns[i, 1] - \
                                conns[i, 0] >= conns[j, 1] - conns[j, 0]:
                            if (
                                conns[
                                    i,
                                    0] <= conns[
                                    j,
                                    0] and conns[
                                    i,
                                    1] >= conns[
                                    j,
                                    0]) or (
                                conns[
                                    i,
                                    0] <= conns[
                                    j,
                                    1] and conns[
                                    i,
                                    1] >= conns[
                                        j,
                                    1]):
                                #% Take the union of connections i and j.
                                newConns[newConnsI, 0] = min(
                                    conns[i, 0], conns[j, 0])
                                newConns[newConnsI, 1] = max(
                                    conns[i, 1], conns[j, 1])
                                newConns[newConnsI, 2] = 0

                                newConnsI += 1
                                connected = True

                        #% Does connection i intersect j?
                        else:
                            if (
                                conns[
                                    i,
                                    0] >= conns[
                                    j,
                                    0] and conns[
                                    i,
                                    0] <= conns[
                                    j,
                                    1]) or (
                                conns[
                                    i,
                                    1] >= conns[
                                    j,
                                    0] and conns[
                                    i,
                                    1] <= conns[
                                        j,
                                    1]):
                                #% Take the union of connections i and j.
                                newConns[newConnsI, 0] = min(
                                    conns[i, 0], conns[j, 0])
                                newConns[newConnsI, 1] = max(
                                    conns[i, 1], conns[j, 1])
                                newConns[newConnsI, 2] = 0
                                newConnsI += 1
                                connected = True

                    #% Connection j wraps.
                    else:
                        #% Add connection i to the beginning of j.
                        justConnected = False  # % did we just connect?
                        if conns[i, 1] >= conns[j, 0]:
                            newConns[
                                newConnsI, 0] = min(
                                conns[
                                    i, 0], conns[
                                    j, 0])
                            newConns[newConnsI, 1] = conns[j, 1]
                            newConns[newConnsI, 2] = 1
                            newConnsI = newConnsI + 1
                            connected = True
                            justConnected = True

                        #% Add connection i to the end of j.
                        if conns[i, 0] <= conns[j, 1]:
                            if justConnected:
                                newConns[
                                    newConnsI - 1,
                                    1] = max(
                                    conns[
                                        i,
                                        1],
                                    conns[
                                        j,
                                        1])
                            else:
                                newConns[newConnsI, 0] = conns[j, 0]
                                newConns[newConnsI, 1] = max(
                                    conns[i, 1], conns[j, 1])
                                newConns[newConnsI, 2] = 1
                                newConnsI = newConnsI + 1
                                connected = True

                #% Are both connections wrapping?
                else:
                    if conns[j, 2]:
                        #% Take the union of connections i and j.
                        newConns[newConnsI, 0] = min(conns[i, 0], conns[j, 0])
                        newConns[newConnsI, 1] = max(conns[i, 1], conns[j, 1])
                        newConns[newConnsI, 2] = 1
                        newConnsI = newConnsI + 1
                        connected = True

                    #% Connection j is continuous.
                    else:
                        #% Add connection j to the beginning of i.
                        justConnected = False  # % did we just connect?
                        if conns[i, 0] <= conns[j, 1]:
                            newConns[
                                newConnsI, 0] = min(
                                conns[
                                    i, 0], conns[
                                    j, 0])
                            newConns[newConnsI, 1] = conns[i, 1]
                            newConns[newConnsI, 2] = 1
                            newConnsI = newConnsI + 1
                            connected = True
                            justConnected = True

                        #% Add connection j to the end of i.
                        if conns[i, 1] >= conns[j, 0]:
                            if justConnected:
                                newConns[
                                    newConnsI - 1,
                                    1] = max(
                                    conns[
                                        i,
                                        1],
                                    conns[
                                        j,
                                        1])
                            else:
                                newConns[newConnsI, 0] = conns[i, 0]
                                newConns[newConnsI, 1] = max(
                                    conns[i, 1], conns[j, 1])
                                newConns[newConnsI, 2] = 1
                                newConnsI = newConnsI + 1
                                connected = True

            #% Add the connection.
            if not connected:
                if newConnsI < newConns.shape[0]:
                    newConns[newConnsI, :] = conns[i, 0:3]
                else:
                    np.vstack((newConns, conns[i, 0:3]))

                newConnsI = newConnsI + 1

        #% Collapse any extra memory.
        newConns = newConns[newConnsI - 1:]

        #% Have we made any new connections?
        prevConnsSize = conns.shape[0]
        conns = newConns
#%%
    return conns


def connectSplits(conns, worm_contour, maxI, minI):
    #%%
    #% Connect the contour splits.
    for i in range(conns.shape[0]):
        #% Connect the continuous contour split.
        if not conns[i, 2]:
            minI = conns[i, 0]
            maxI = conns[i, 1]
            minP = worm_contour[minI, :]
            maxP = worm_contour[maxI, :]
            points = maxI - minI + 1
            worm_contour[
                minI:maxI + 1,
                0] = np.round(
                np.linspace(
                    minP[0],
                    maxP[0],
                    points))
            worm_contour[
                minI:maxI + 1,
                1] = np.round(
                np.linspace(
                    minP[1],
                    maxP[1],
                    points))

        #% Connect the wrapping contour split.
        else:
            minI = conns[i, 1]
            maxI = conns[i, 0]
            minP = worm_contour[minI, :]
            maxP = worm_contour[maxI, :]
            points = minI + worm_contour.shape[0] - maxI + 1
            interPoints = np.zeros((points, 2))
            interPoints[:, 0] = np.linspace(maxP[0], minP[0], points)
            interPoints[:, 1] = np.linspace(maxP[1], minP[1], points)
            worm_contour[maxI:, :] = np.round(interPoints[0:-minI - 1, :])
            worm_contour[:minI + 1, :] = np.round(interPoints[-minI - 1:, :])
    #%%
    return worm_contour


def cleanWorm(contour, cWormSegs):
    '''%CLEANWORM Clean up the worm contour by connecting any splits ends.
    %
    %   CONTOUR = CLEANWORM(CONTOUR, WORMSEGSIZE)
    %
    %   Note: the worm's contour is still rough, especially at any split ends.
    %         Therefore, index lengths, as opposed to chain-code lengths, are
    %         used as the distance metric over the worm's contour.
    %
    %   Inputs:
    %       contour     - the clockwise, circularly-connected worm contour.
    %       wormSegSize - the size (in contour points) of a worm segment.
    %                     Note: The worm's contour is roughly divided into 50
    %                     segments of musculature (i.e., hinges that represent
    %                     degrees of freedom).
    %                     Warning: before cleaning, the length of the contour
    %                     can vary significantly: from 1/4 its correct size, if
    %                     the worm is coiled up with its head and tail touching
    %                     its body, 180 degrees apart on the coil; to 2 times
    %                     its correct size, if the head and tail are both split
    %                     by invaginations that reach 1/4 into its body.
    %                     Additionally, there are various permutations in
    %                     between these extremes. Therefore, we use carefully
    %                     chosen approximations that are fail-safe to within a
    %                     large margin. Moreover, we use several other tricks
    %                     to ensure we don't incorrectly heal false worm splits
    %                     (e.g., we check for a sharp concavity before joining
    %                     sharp convexities). But, we remain labile in extreme
    %                     cases (e.g., omega bends where the head and tail are
    %                     very proximal).
    %
    %   Output:
    %       contour - the cleaned up worm contour.
    %
    %
    % © Medical Research Council 2012
    % You will not remove any copyright or other notices from the Software;
    % you must reproduce all copyright notices and other proprietary
    % notices on any copies of the Software.'''
    wormSegSize = round(contour.shape[0] / cWormSegs)
    angles = circCurvature(contour, wormSegSize)

    #% On a small scale, noise causes contour imperfections that shift an angle
    #% from its correct location. Therefore, blurring angles by averaging them
    #% with their neighbors can localize them better.
    blurLength = np.ceil(wormSegSize / 2.)
    mAngles = circSmooth(angles, blurLength)

    #% Is the worm contour split at the head and/or tail?
    #% Note: often the head and tail have light colored internals that, when
    #% binarized, split the head and/or tail into two or more pieces.
    #% Note 2: We don't use the blurred angles for concavities. Unfortunately,
    #% blurring can erase high-frequency minima. Moreover, we don't need
    #% any improvements in localizing these concavities.
#%%
    maxP, maxI = extremaPeaksCircDist(1, mAngles, wormSegSize)
    minP, minI = extremaPeaksCircDist(-1, angles, wormSegSize)

#    if DEBUG:
#        plt.figure()
#        plt.plot(mAngles)
#        plt.plot(angles)
#
#        plt.plot(minI, minP, 'og')
#        plt.plot(maxI, maxP, 'xr')

    maxI = maxI[maxP > 60]
    minI = minI[minP < -90]
    #% Do we have multiple sharp convexities (potential contour splits) that are
    #% nearby on the contour and/or, nearby in distance and separated by a sharp
    #% concavity?
    nearSize = 2 * wormSegSize  # % a nearby distance
    if minI.size > 0 or (maxI.size > 0 and (
            np.any(np.diff(maxI)) or maxI[0] + mAngles.size - maxI[-1])):

        conns = getPossibleConnections(contour, maxI, minI, nearSize)
        #% Clean up the contour.
        if conns.shape[0] > 1:
            conns = connectPeaks(conns, maxI)
            conns = connectConnections(conns)
            contour = connectSplits(conns, contour, maxI, minI)
            #% Clean up the contour.
            contour = cleanContour(contour)

    if contour.shape[0] > 2:
        contour, keep = removeSmallSegments(contour)

    return contour
