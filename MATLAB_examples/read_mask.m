%filename = '/Volumes/behavgenom$/GeckoVideo/Compressed/20150216/CaptureTest_90pc_Ch1_16022015_174636.hdf5';
filename = '/Volumes/behavgenom_archive$/Serena/CurrentDatasetSpiking/MaskedVideos/recording52/recording52.1g100-350TIFF/recording52.1g_X1.hdf5';

%get the chunksize
mask_info =  h5info(filename, '/mask');
chunkSize = mask_info.ChunkSize; %image size in my format

%%
for frame_number = 1:25:200
    image = h5read(filename, '/mask', [1,1,frame_number], chunkSize)';
    figure, imshow(image)
end