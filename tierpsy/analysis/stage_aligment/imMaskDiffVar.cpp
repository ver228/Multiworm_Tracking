#include <mex.h>

void mexFunction(int nlhs, mxArray *plhs[], int nrhs, const mxArray *prhs[])
{
    uint8_T *image1 = (uint8_T *)mxGetData(prhs[0]);
    uint8_T *image2 = (uint8_T *)mxGetData(prhs[1]);
    size_t tot_pix = mxGetNumberOfElements(prhs[0]);
    
    plhs[0] = mxCreateNumericMatrix(1,1,mxDOUBLE_CLASS,mxREAL);
    
    double* var_diff = mxGetPr(plhs[0]);
    
    double mean_x = 0;
    double sum_x2 = 0;
    
    double abs_diff = 0;
    double tot_valid = 0;
    
    for (size_t i = 0; i<tot_pix; i++){
        if (image1[i] > 0 && image2[i] > 0)
        {
            abs_diff = double(image1[i]) - double(image2[i]);
            mean_x += abs_diff;
            sum_x2 += abs_diff*abs_diff;
            tot_valid++;
        }
    }
    mean_x /= tot_valid;
    var_diff[0] = sum_x2/tot_valid - mean_x*mean_x;
}