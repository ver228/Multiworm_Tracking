function [DATA]=getFileData2(data_base_file)
%%
DATA = [];

FID = fopen(data_base_file,'r');
header = strsplit(fgetl(FID), ',');

for ii = 1:numel(header)
    DATA.(header{ii}) = {};
end

row_n = 0;
while ~feof(FID)
    row_n = row_n + 1;    
    row_data = strsplit(fgetl(FID), ',');
    
    for ii = 1:numel(header)
        DATA.(header{ii}){row_n} = row_data{ii};
    end
end
fclose(FID);
%%
for ii = 1:numel(header)
    try
        DATA.(header{ii}) = cellfun(@str2num, DATA.(header{ii}));
    catch 
    end
end
end